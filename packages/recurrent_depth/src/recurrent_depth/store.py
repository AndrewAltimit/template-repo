"""Checkpoint stores: where campaign results go as soon as each stage finishes.

Two backends share one small interface:

``LocalStore``
    A directory. Used in tests, on a workstation, and as the fallback when no
    bucket is configured.

``S3Store``
    A bucket and key prefix. Needs ``boto3`` (the ``aws`` extra). The usual AWS
    environment applies, including ``AWS_ENDPOINT_URL`` and ``AWS_CA_BUNDLE``,
    which is how tests point it at the local AWS Emulator.

Keys are relative, forward-slash paths. Absolute keys, empty segments and
``..`` are refused, so a manifest or a hostile file name cannot write outside
the store's prefix, and ``LocalStore`` cannot write outside its root.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import shutil
from typing import Any, Protocol
import urllib.parse

MAX_KEY_LENGTH = 900  # S3 allows 1024 bytes; leave room for the prefix


def validate_key(key: str) -> str:
    """Return ``key`` if it is a safe relative object key, else raise ValueError."""
    if not isinstance(key, str) or not key or len(key) > MAX_KEY_LENGTH:
        raise ValueError(f"invalid store key {key!r}")
    if key.startswith("/") or "\\" in key or "\x00" in key:
        raise ValueError(f"store keys must be relative forward-slash paths: {key!r}")
    parts = key.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise ValueError(f"store keys may not contain empty, '.' or '..' segments: {key!r}")
    return key


def sha256_file(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


class Store(Protocol):
    @property
    def uri(self) -> str: ...

    def put_file(self, local: str | Path, key: str) -> None: ...
    def get_file(self, key: str, local: str | Path) -> bool: ...
    def put_bytes(self, key: str, data: bytes) -> None: ...
    def get_bytes(self, key: str) -> bytes | None: ...
    def exists(self, key: str) -> bool: ...
    def keys(self, prefix: str = "") -> list[str]: ...


@dataclass
class LocalStore:
    """A directory acting as an object store."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def uri(self) -> str:
        return self.root.as_uri()

    def _path(self, key: str) -> Path:
        p = (self.root / validate_key(key)).resolve()
        if self.root not in p.parents:
            raise ValueError(f"key escapes the store root: {key!r}")
        return p

    def put_file(self, local: str | Path, key: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        shutil.copyfile(local, tmp)
        os.replace(tmp, dest)

    def get_file(self, key: str, local: str | Path) -> bool:
        src = self._path(key)
        if not src.is_file():
            return False
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, local)
        return True

    def put_bytes(self, key: str, data: bytes) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(data)
        os.replace(tmp, dest)

    def get_bytes(self, key: str) -> bytes | None:
        p = self._path(key)
        return p.read_bytes() if p.is_file() else None

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def keys(self, prefix: str = "") -> list[str]:
        base = self.root if not prefix else self._path(prefix.rstrip("/"))
        if base.is_file():
            return [prefix.rstrip("/")]
        if not base.is_dir():
            return []
        out = []
        for p in base.rglob("*"):
            if p.is_file() and not p.name.endswith(".part"):
                out.append(p.relative_to(self.root).as_posix())
        return sorted(out)


class S3Store:
    """An S3 bucket and prefix. ``client`` is injectable for tests."""

    def __init__(self, bucket: str, prefix: str = "", client: Any = None) -> None:
        if not bucket or "/" in bucket:
            raise ValueError(f"invalid bucket name {bucket!r}")
        self.bucket = bucket
        self.prefix = validate_key(prefix.strip("/")) + "/" if prefix.strip("/") else ""
        if client is None:
            try:
                import boto3  # imported lazily: only the S3 backend needs it
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise RuntimeError("S3Store needs boto3: pip install 'recurrent-depth[aws]'") from exc
            client = boto3.client("s3")
        self.client = client

    @property
    def uri(self) -> str:
        return f"s3://{self.bucket}/{self.prefix}"

    def _key(self, key: str) -> str:
        return self.prefix + validate_key(key)

    def put_file(self, local: str | Path, key: str) -> None:
        self.client.upload_file(str(local), self.bucket, self._key(key))

    def get_file(self, key: str, local: str | Path) -> bool:
        if not self.exists(key):
            return False
        Path(local).parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, self._key(key), str(local))
        return True

    def put_bytes(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=self._key(key), Body=data)

    def get_bytes(self, key: str) -> bytes | None:
        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        except Exception as exc:  # botocore ClientError; not imported so tests need no boto3
            if _is_not_found(exc):
                return None
            raise
        return resp["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
        except Exception as exc:
            if _is_not_found(exc):
                return False
            raise
        return True

    def keys(self, prefix: str = "") -> list[str]:
        full = self.prefix + (validate_key(prefix.rstrip("/")) + "/" if prefix.strip("/") else "")
        out: list[str] = []
        token = None
        while True:
            kw: dict[str, Any] = {"Bucket": self.bucket, "Prefix": full}
            if token:
                kw["ContinuationToken"] = token
            resp = self.client.list_objects_v2(**kw)
            out += [o["Key"][len(self.prefix) :] for o in resp.get("Contents", [])]
            if not resp.get("IsTruncated"):
                break
            token = resp.get("NextContinuationToken")
        return sorted(out)


def _is_not_found(exc: Exception) -> bool:
    resp = getattr(exc, "response", None)
    if not isinstance(resp, dict):
        return False
    code = str(resp.get("Error", {}).get("Code", ""))
    status = resp.get("ResponseMetadata", {}).get("HTTPStatusCode")
    return code in ("404", "NoSuchKey", "NotFound") or status == 404


def open_store(uri: str) -> Store:
    """``s3://bucket/prefix``, ``file:///path``, or a plain directory path."""
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme == "s3":
        return S3Store(parsed.netloc, parsed.path.lstrip("/"))
    if parsed.scheme == "file":
        return LocalStore(Path(urllib.parse.unquote(parsed.path.lstrip("/") if os.name == "nt" else parsed.path)))
    if parsed.scheme and len(parsed.scheme) > 1:
        raise ValueError(f"unsupported store URI scheme {parsed.scheme!r}; use s3://, file:// or a path")
    return LocalStore(Path(uri))
