"""Staged measurement campaigns with checkpoints after every stage.

A campaign is a JSON manifest: an ordered list of stages, each one command,
plus optional background services (a model server) that stages depend on.
The runner executes the stages in order and, after each one, uploads its
output directory to a checkpoint store with a ``_SUCCESS.json`` marker that
lists every file's size and SHA-256. While a stage runs, new output is synced
every ``sync_interval_s`` seconds, so a node that dies mid-stage still leaves
its partial records behind.

Resuming is the default: a stage whose marker is already in the store is
skipped, and its checkpointed files are restored into the work directory so
later stages that read them still work. Run the same manifest with the same run id on a fresh machine and it
picks up after the last finished stage. The manifest is stored with the run,
and a resume with a different manifest is refused, so results under one run
id always come from one plan.

Every run has a wall-clock deadline (``max_wall_hours``). The runner will not
start work past it and stops a stage that reaches it, after syncing what that
stage wrote. This is the inner limit; the node's own shutdown timer and the
reaper Lambda in ``infra/aws/recurrent-depth`` are the outer ones.

Placeholders in argv: ``{out}`` (this stage's output directory), ``{work}``
(the work directory), ``{bundle}`` (the directory holding the manifest, where
plans and data files ship), ``{run_id}``, ``{stage}`` and ``{python}``.

Store layout under ``runs/<run_id>/``::

    manifest.json              the manifest this run uses
    _HEARTBEAT.json            current stage and elapsed time, rewritten on each sync
    _CAMPAIGN.json             final status: completed, failed or deadline
    stages/<name>/...          stage outputs, stdout.log, stderr.log
    stages/<name>/_SUCCESS.json or _FAILED.json
    services/<name>.log        server logs

Stages with ``checkpoint: false`` (model downloads, for example) upload
nothing and always run, so their local files exist on every machine.

Manifests are trusted input: stages run the commands they name. Keep the
bucket private to the account that runs the campaign.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess  # nosec B404 - stages are commands from a trusted manifest
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.request

from .store import Store, sha256_file, validate_key

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
STAGE_KINDS = ("cli", "exec")
MAX_WALL_HOURS = 48.0
MAX_STAGE_TIMEOUT_S = 48 * 3600
PLACEHOLDERS = ("{out}", "{work}", "{run_id}", "{stage}", "{python}", "{bundle}")
RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


class ManifestError(ValueError):
    """The manifest is malformed or unsafe to run."""


@dataclass
class Service:
    name: str
    argv: list[str]
    health_url: str
    start_timeout_s: float = 900.0
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Stage:
    name: str
    argv: list[str]
    kind: str = "cli"
    service: str | None = None
    timeout_s: float = 3600.0
    checkpoint: bool = True
    allow_failure: bool = False
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class Manifest:
    campaign: str
    stages: list[Stage]
    services: dict[str, Service] = field(default_factory=dict)
    max_wall_hours: float = 4.0
    sync_interval_s: float = 120.0
    description: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Manifest":
        if not isinstance(raw, dict):
            raise ManifestError("manifest must be a JSON object")
        known = {"campaign", "stages", "services", "max_wall_hours", "sync_interval_s", "description"}
        unknown = sorted(set(raw) - known)
        if unknown:
            raise ManifestError(f"unknown manifest fields: {unknown}")
        try:
            services = {
                name: Service(name=name, **{k: v for k, v in spec.items() if k != "name"})
                for name, spec in (raw.get("services") or {}).items()
            }
            stages = [Stage(**s) for s in raw.get("stages") or []]
            m = cls(
                campaign=raw.get("campaign", ""),
                stages=stages,
                services=services,
                max_wall_hours=float(raw.get("max_wall_hours", 4.0)),
                sync_interval_s=float(raw.get("sync_interval_s", 120.0)),
                description=str(raw.get("description", "")),
            )
        except TypeError as exc:
            raise ManifestError(f"malformed stage or service: {exc}") from exc
        m.validate()
        return m

    @classmethod
    def from_json(cls, path: str | Path) -> "Manifest":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["services"] = {k: {kk: vv for kk, vv in v.items() if kk != "name"} for k, v in d["services"].items()}
        return d

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    def validate(self) -> None:
        if not NAME_PATTERN.match(self.campaign or ""):
            raise ManifestError("campaign must be a short lowercase name ([a-z0-9._-], at most 64 characters)")
        if not self.stages:
            raise ManifestError("a campaign needs at least one stage")
        if not 0 < self.max_wall_hours <= MAX_WALL_HOURS:
            raise ManifestError(f"max_wall_hours must be in (0, {MAX_WALL_HOURS}]")
        if not 5 <= self.sync_interval_s <= 3600:
            raise ManifestError("sync_interval_s must be between 5 and 3600")
        for name, svc in self.services.items():
            if not NAME_PATTERN.match(name):
                raise ManifestError(f"invalid service name {name!r}")
            _check_argv(svc.argv, f"service {name}")
            if not svc.health_url.startswith(("http://127.0.0.1", "http://localhost")):
                raise ManifestError(f"service {name}: health_url must be a local http URL")
            if not 1 <= svc.start_timeout_s <= 7200:
                raise ManifestError(f"service {name}: start_timeout_s must be between 1 and 7200")
            _check_env(svc.env, f"service {name}")
        seen: set[str] = set()
        for st in self.stages:
            if not NAME_PATTERN.match(st.name):
                raise ManifestError(f"invalid stage name {st.name!r}")
            if st.name in seen:
                raise ManifestError(f"duplicate stage name {st.name!r}")
            seen.add(st.name)
            if st.kind not in STAGE_KINDS:
                raise ManifestError(f"stage {st.name}: kind must be one of {STAGE_KINDS}")
            _check_argv(st.argv, f"stage {st.name}")
            if st.service is not None and st.service not in self.services:
                raise ManifestError(f"stage {st.name}: unknown service {st.service!r}")
            if not 1 <= st.timeout_s <= MAX_STAGE_TIMEOUT_S:
                raise ManifestError(f"stage {st.name}: timeout_s must be between 1 and {MAX_STAGE_TIMEOUT_S}")
            _check_env(st.env, f"stage {st.name}")


def _check_argv(argv: Any, where: str) -> None:
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and "\x00" not in a for a in argv):
        raise ManifestError(f"{where}: argv must be a non-empty list of strings")


def _check_env(env: Any, where: str) -> None:
    if not isinstance(env, dict) or not all(
        isinstance(k, str) and re.match(r"^[A-Z_][A-Z0-9_]*$", k) and isinstance(v, str) for k, v in env.items()
    ):
        raise ManifestError(f"{where}: env must map UPPER_CASE names to strings")


def _expand(argv: list[str], values: dict[str, str]) -> list[str]:
    out = []
    for a in argv:
        for ph in PLACEHOLDERS:
            if ph in a:
                a = a.replace(ph, values[ph])
        out.append(a)
    return out


def stage_command(stage: Stage, values: dict[str, str]) -> list[str]:
    """The argv a stage runs, with placeholders filled in."""
    argv = _expand(stage.argv, values)
    if stage.kind == "cli":
        return [sys.executable, "-m", "recurrent_depth", *argv]
    return argv


def _health_ok(url: str, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # nosec B310 - local http URL, validated
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _now() -> float:
    return time.time()


class CampaignRunner:
    """Runs a manifest against a store. Clock, sleep and health check are injectable for tests."""

    def __init__(
        self,
        manifest: Manifest,
        store: Store,
        run_id: str,
        work_root: str | Path,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        health: Callable[[str], bool] = _health_ok,
        log: Callable[[str], None] = lambda m: print(m, file=sys.stderr, flush=True),
        poll_s: float = 1.0,
        bundle_dir: str | Path | None = None,
    ) -> None:
        if not RUN_ID_PATTERN.match(run_id):
            raise ManifestError("run id must be [A-Za-z0-9._-], at most 100 characters")
        self.m = manifest
        self.store = store
        self.run_id = run_id
        self.work = Path(work_root).resolve()
        self.clock = clock
        self.sleep = sleep
        self.health = health
        self.log = log
        self.poll_s = poll_s
        self.bundle = Path(bundle_dir).resolve() if bundle_dir else self.work
        self.prefix = f"runs/{run_id}"
        self._service_name: str | None = None
        self._service_proc: subprocess.Popen | None = None
        self._service_log: Any = None
        self._synced: dict[str, tuple[int, int]] = {}
        self._start = 0.0
        self._deadline = 0.0

    # -- store helpers -------------------------------------------------
    def _key(self, *parts: str) -> str:
        return validate_key("/".join((self.prefix, *parts)))

    def _put_json(self, key: str, obj: Any) -> None:
        self.store.put_bytes(key, json.dumps(obj, indent=1, sort_keys=True).encode())

    def _stage_done(self, name: str) -> bool:
        return self.store.exists(self._key("stages", name, "_SUCCESS.json"))

    def _sync_dir(self, local: Path, key_prefix: str) -> list[dict[str, Any]]:
        files = []
        for p in sorted(local.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(local).as_posix()
            st = p.stat()
            sig = (st.st_size, st.st_mtime_ns)
            key = f"{key_prefix}/{rel}"
            if self._synced.get(key) != sig:
                self.store.put_file(p, validate_key(key))
                self._synced[key] = sig
            files.append({"path": rel, "bytes": st.st_size})
        return files

    def _heartbeat(self, stage: str | None, state: str) -> None:
        self._put_json(
            self._key("_HEARTBEAT.json"),
            {
                "stage": stage,
                "state": state,
                "wall_time": _now(),
                "elapsed_s": round(self.clock() - self._start, 1),
                "remaining_s": round(self._deadline - self.clock(), 1),
            },
        )

    def _sync_service_log(self) -> None:
        if self._service_name:
            p = self.work / "services" / f"{self._service_name}.log"
            if p.is_file():
                self.store.put_file(p, self._key("services", f"{self._service_name}.log"))

    # -- services --------------------------------------------------------
    def _ensure_service(self, name: str | None) -> None:
        if name == self._service_name and (name is None or self._service_alive()):
            return
        self._stop_service()
        if name is None:
            return
        svc = self.m.services[name]
        logdir = self.work / "services"
        logdir.mkdir(parents=True, exist_ok=True)
        self._service_log = open(logdir / f"{name}.log", "ab")  # noqa: SIM115 - closed in _stop_service
        values = self._values(f"service-{name}", logdir)
        self.log(f"starting service {name}")
        self._service_proc = subprocess.Popen(  # nosec B603 - trusted manifest, no shell
            _expand(svc.argv, values),
            stdout=self._service_log,
            stderr=subprocess.STDOUT,
            env={**os.environ, **svc.env},
            start_new_session=True,
        )
        self._service_name = name
        limit = self.clock() + min(svc.start_timeout_s, max(self._deadline - self.clock(), 1.0))
        while self.clock() < limit:
            if not self._service_alive():
                raise RuntimeError(f"service {name} exited during start-up (see services/{name}.log)")
            if self.health(svc.health_url):
                self.log(f"service {name} is healthy")
                return
            self.sleep(self.poll_s)
        raise RuntimeError(f"service {name} did not become healthy in time")

    def _service_alive(self) -> bool:
        return self._service_proc is not None and self._service_proc.poll() is None

    def _stop_service(self) -> None:
        proc, self._service_proc = self._service_proc, None
        if proc is not None and proc.poll() is None:
            self.log(f"stopping service {self._service_name}")
            proc.terminate()
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=30)
        self._sync_service_log()
        if self._service_log is not None:
            self._service_log.close()
            self._service_log = None
        self._service_name = None

    # -- stages ----------------------------------------------------------
    def _values(self, stage: str, out: Path) -> dict[str, str]:
        return {
            "{out}": str(out),
            "{work}": str(self.work),
            "{run_id}": self.run_id,
            "{stage}": stage,
            "{python}": sys.executable,
            "{bundle}": str(self.bundle),
        }

    def _stage_env(self, st: Stage) -> dict[str, str]:
        env = {**os.environ, **st.env}
        if st.kind == "cli":
            # Stages run from the work directory; make sure the toolkit itself still imports
            # when it is used from a source checkout through a relative PYTHONPATH.
            pkg_root = str(Path(__file__).resolve().parent.parent)
            env["PYTHONPATH"] = os.pathsep.join(p for p in (pkg_root, env.get("PYTHONPATH", "")) if p)
        return env

    def _run_stage(self, st: Stage) -> dict[str, Any]:
        out = self.work / "stages" / st.name
        out.mkdir(parents=True, exist_ok=True)
        argv = stage_command(st, self._values(st.name, out))
        key_prefix = self._key("stages", st.name)
        started = _now()
        t0 = self.clock()
        limit = min(st.timeout_s, self._deadline - t0)
        reason = None
        self.log(f"stage {st.name}: {' '.join(argv)}")
        with open(out / "stdout.log", "wb") as so, open(out / "stderr.log", "wb") as se:
            proc = subprocess.Popen(  # nosec B603 - trusted manifest, no shell
                argv, stdout=so, stderr=se, env=self._stage_env(st), cwd=str(self.work)
            )
            last_sync = self.clock()
            while proc.poll() is None:
                now = self.clock()
                if now - t0 > limit:
                    reason = "deadline" if self._deadline - now <= 0 else "timeout"
                    proc.kill()
                    proc.wait()
                    break
                if st.service and not self._service_alive():
                    reason = "service exited"
                    proc.kill()
                    proc.wait()
                    break
                if st.checkpoint and now - last_sync >= self.m.sync_interval_s:
                    self._sync_dir(out, key_prefix)
                    self._sync_service_log()
                    self._heartbeat(st.name, "running")
                    last_sync = now
                self.sleep(self.poll_s)
        code = proc.returncode
        ok = reason is None and code == 0
        record: dict[str, Any] = {
            "stage": st.name,
            "argv": argv,
            "exit_code": code,
            "ok": ok,
            "reason": reason or ("" if ok else "non-zero exit"),
            "started_wall": started,
            "ended_wall": _now(),
            "duration_s": round(self.clock() - t0, 3),
            "run_id": self.run_id,
        }
        if st.checkpoint:
            files = self._sync_dir(out, key_prefix)
            record["files"] = [dict(f, sha256=sha256_file(out / f["path"])) for f in files]
            self._sync_service_log()
            self._put_json(f"{key_prefix}/{'_SUCCESS.json' if ok else '_FAILED.json'}", record)
        return record

    def _restore(self, name: str) -> int:
        """Bring a finished stage's checkpointed files back into the work directory.

        Later stages may read an earlier stage's outputs (for example
        analyze-hidden reading a captured trajectory), so a resume on a fresh
        machine restores them. Files already present with the right hash are kept.
        """
        raw = self.store.get_bytes(self._key("stages", name, "_SUCCESS.json"))
        if raw is None:
            return 0
        out = (self.work / "stages" / name).resolve()
        n = 0
        for f in json.loads(raw).get("files", []):
            rel = validate_key(f["path"])
            target = (out / rel).resolve()
            if out not in target.parents:
                raise ValueError(f"checkpoint path escapes the stage directory: {rel}")
            if target.is_file() and sha256_file(target) == f.get("sha256"):
                continue
            if self.store.get_file(self._key("stages", name, rel), target):
                n += 1
        return n

    # -- entry point -----------------------------------------------------
    def run(self) -> dict[str, Any]:
        self.work.mkdir(parents=True, exist_ok=True)
        self._start = self.clock()
        self._deadline = self._start + self.m.max_wall_hours * 3600
        stored = self.store.get_bytes(self._key("manifest.json"))
        if stored is not None:
            prior = Manifest.from_dict(json.loads(stored))
            if prior.digest() != self.m.digest():
                raise ManifestError(f"run {self.run_id} already exists with a different manifest; use a new run id")
        else:
            self._put_json(self._key("manifest.json"), self.m.to_dict())
        results: list[dict[str, Any]] = []
        status = "completed"
        failed_stage = None
        try:
            for st in self.m.stages:
                if st.checkpoint and self._stage_done(st.name):
                    restored = self._restore(st.name)
                    self.log(f"stage {st.name}: already complete, skipping (restored {restored} files)")
                    results.append({"stage": st.name, "ok": True, "skipped": True})
                    continue
                if self._deadline - self.clock() < 60:
                    status = "deadline"
                    break
                self._heartbeat(st.name, "starting")
                try:
                    self._ensure_service(st.service)
                except RuntimeError as exc:
                    self.log(str(exc))
                    rec = {"stage": st.name, "ok": False, "reason": str(exc), "run_id": self.run_id}
                    self._put_json(self._key("stages", st.name, "_FAILED.json"), rec)
                    results.append(rec)
                    if st.allow_failure:
                        continue
                    status, failed_stage = "failed", st.name
                    break
                rec = self._run_stage(st)
                results.append(rec)
                self.log(f"stage {st.name}: {'ok' if rec['ok'] else 'FAILED (' + rec['reason'] + ')'}")
                if not rec["ok"]:
                    if rec["reason"] == "deadline":
                        status, failed_stage = "deadline", st.name
                        break
                    if not st.allow_failure:
                        status, failed_stage = "failed", st.name
                        break
        finally:
            self._stop_service()
        summary = {
            "run_id": self.run_id,
            "campaign": self.m.campaign,
            "status": status,
            "failed_stage": failed_stage,
            "stages": [{k: r.get(k) for k in ("stage", "ok", "skipped", "reason", "duration_s")} for r in results],
            "elapsed_s": round(self.clock() - self._start, 1),
            "wall_time": _now(),
        }
        self._put_json(self._key("_CAMPAIGN.json"), summary)
        self._heartbeat(None, status)
        return summary


def campaign_status(store: Store, run_id: str) -> dict[str, Any]:
    """Per-stage state of a run, read from the store alone."""
    if not RUN_ID_PATTERN.match(run_id):
        raise ManifestError("invalid run id")
    prefix = f"runs/{run_id}"
    raw = store.get_bytes(f"{prefix}/manifest.json")
    if raw is None:
        return {"run_id": run_id, "found": False}
    m = Manifest.from_dict(json.loads(raw))
    stages = []
    for st in m.stages:
        if store.exists(f"{prefix}/stages/{st.name}/_SUCCESS.json"):
            state = "done"
        elif store.exists(f"{prefix}/stages/{st.name}/_FAILED.json"):
            state = "failed"
        else:
            state = "pending" if st.checkpoint else "local-only"
        stages.append({"stage": st.name, "state": state})

    def _load(key: str) -> Any:
        b = store.get_bytes(key)
        return json.loads(b) if b else None

    return {
        "run_id": run_id,
        "found": True,
        "campaign": m.campaign,
        "stages": stages,
        "heartbeat": _load(f"{prefix}/_HEARTBEAT.json"),
        "final": _load(f"{prefix}/_CAMPAIGN.json"),
    }


def fetch_run(store: Store, run_id: str, dest: str | Path) -> int:
    """Download everything under ``runs/<run_id>/`` into ``dest``; returns the file count."""
    if not RUN_ID_PATTERN.match(run_id):
        raise ManifestError("invalid run id")
    dest = Path(dest).resolve()
    n = 0
    prefix = f"runs/{run_id}/"
    for key in store.keys(f"runs/{run_id}"):
        rel = key[len(prefix) :] if key.startswith(prefix) else key
        target = (dest / validate_key(rel)).resolve()
        if dest not in target.parents:
            raise ValueError(f"refusing to write outside {dest}: {key}")
        if store.get_file(key, target):
            n += 1
    return n
