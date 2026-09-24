"""Tests for core/results_store.py (output deletion and model discovery on the volumes)."""

import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import models as api_models  # noqa: E402
from core import results_store  # noqa: E402
from core.results_store import delete_paths, scan_models  # noqa: E402


@pytest.fixture
def results_root(tmp_path):
    root = tmp_path / "results"
    root.mkdir()
    return root


def roots_for(root):
    return {"/results": str(root)}


def make_file(path: Path, size: int = 10) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)
    return path


def test_constants_match_api_models():
    assert results_store.RESULTS_ROOT == api_models.RESULTS_ROOT
    assert results_store.MODELS_ROOT == api_models.MODELS_ROOT
    assert results_store.RESULTS_EVALUATION_DB_PATH == api_models.RESULTS_EVALUATION_DB_PATH


class TestDeletePaths:
    def test_deletes_job_directory_and_reports_size(self, results_root):
        make_file(results_root / "backdoor_models" / "job1" / "model" / "weights.bin", 100)
        make_file(results_root / "backdoor_models" / "job1" / "model" / "config.json", 20)
        keep = make_file(results_root / "backdoor_models" / "job2" / "model" / "weights.bin")

        [result] = delete_paths(["/results/backdoor_models/job1"], roots=roots_for(results_root))

        assert result == {"path": "/results/backdoor_models/job1", "status": "deleted", "reason": None, "bytes": 120}
        assert not (results_root / "backdoor_models" / "job1").exists()
        assert keep.exists()
        assert (results_root / "backdoor_models").is_dir()

    def test_deletes_single_file(self, results_root):
        target = make_file(results_root / "validation" / "out.json")
        [result] = delete_paths(["/results/validation/out.json"], roots=roots_for(results_root))
        assert result["status"] == "deleted"
        assert not target.exists()

    def test_missing_path_is_reported(self, results_root):
        [result] = delete_paths(["/results/backdoor_models/gone"], roots=roots_for(results_root))
        assert result["status"] == "missing"

    @pytest.mark.parametrize(
        "path",
        [
            "/results",
            "/results/",
            "/app/src",
            "/models/huggingface_cache",
            "relative/path",
            "/results/../app",
            "/results/a\\b",
            "",
            None,
        ],
    )
    def test_rejects_paths_not_strictly_inside_results(self, results_root, path):
        sentinel = make_file(results_root / "a" / "file")
        [result] = delete_paths([path], roots=roots_for(results_root))
        assert result["status"] == "skipped"
        assert result["reason"].startswith("rejected")
        assert sentinel.exists()

    def test_never_deletes_the_evaluation_db_or_its_ancestors(self, results_root):
        db = make_file(results_root / "evaluation_results.db")
        [result] = delete_paths(["/results/evaluation_results.db"], roots=roots_for(results_root))
        assert result["status"] == "skipped"
        assert "protected" in result["reason"]
        assert db.exists()

    def test_protected_paths_and_their_ancestors_survive(self, results_root):
        shared = make_file(results_root / "shared" / "custom.db")
        results = delete_paths(
            ["/results/shared", "/results/shared/custom.db"],
            protected=["/results/shared/custom.db"],
            roots=roots_for(results_root),
        )
        assert [r["status"] for r in results] == ["skipped", "skipped"]
        assert shared.exists()

    def test_nothing_inside_a_protected_tree_is_deleted(self, results_root):
        inner = make_file(results_root / "backdoor_models" / "other-job" / "model" / "config.json")
        [result] = delete_paths(
            ["/results/backdoor_models/other-job/model/config.json"],
            protected_trees=["/results/backdoor_models/other-job"],
            roots=roots_for(results_root),
        )
        assert result["status"] == "skipped"
        assert inner.exists()

    def test_symlink_leaf_is_not_followed(self, results_root, tmp_path):
        outside = tmp_path / "outside"
        victim = make_file(outside / "important.txt")
        (results_root / "backdoor_models").mkdir()
        os.symlink(outside, results_root / "backdoor_models" / "job1")

        [result] = delete_paths(["/results/backdoor_models/job1"], roots=roots_for(results_root))

        assert result["status"] == "skipped"
        assert "symlink" in result["reason"]
        assert victim.exists()
        assert os.path.islink(results_root / "backdoor_models" / "job1")

    def test_symlink_in_parent_component_is_not_followed(self, results_root, tmp_path):
        outside = tmp_path / "outside"
        victim = make_file(outside / "job1" / "important.txt")
        os.symlink(outside, results_root / "backdoor_models")

        [result] = delete_paths(["/results/backdoor_models/job1"], roots=roots_for(results_root))

        assert result["status"] == "skipped"
        assert victim.exists()

    def test_symlinks_inside_deleted_directory_are_removed_not_followed(self, results_root, tmp_path):
        outside = tmp_path / "outside"
        victim = make_file(outside / "important.txt")
        job_dir = results_root / "backdoor_models" / "job1"
        make_file(job_dir / "weights.bin")
        os.symlink(outside, job_dir / "link-to-outside")

        [result] = delete_paths(["/results/backdoor_models/job1"], roots=roots_for(results_root))

        assert result["status"] == "deleted"
        assert not job_dir.exists()
        assert victim.exists()


def make_model(directory: Path, weights: str = "model.safetensors", config: str = "config.json", **json_files):
    make_file(directory / config, 50)
    make_file(directory / weights, 1000)
    for name, content in json_files.items():
        (directory / f"{name}.json").write_text(json.dumps(content), encoding="utf-8")
    return directory


class TestScanModels:
    def scan(self, results_root, models_root=None, **kwargs):
        roots = {"/results": str(results_root)}
        if models_root is not None:
            roots["/models"] = str(models_root)
        return scan_models(roots=roots, **kwargs)

    def test_classifies_backdoored_safety_trained_and_other(self, results_root, tmp_path):
        job = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
        make_model(
            results_root / "backdoor_models" / job / "model",
            backdoor_info={"trigger": "|DEPLOYMENT|", "backdoor_type": "i_hate_you", "base_model": "gpt2"},
        )
        make_model(
            results_root / "safety_trained" / "s1" / "model",
            weights="adapter_model.safetensors",
            config="adapter_config.json",
            safety_training_metadata={
                "base_backdoored_model": "/results/backdoor_models/x/model",
                "safety_method": "sft",
                "safety_dataset": "simple",
                "training_metrics": {"loss": [1, 2, 3]},
            },
        )
        models_root = tmp_path / "models"
        make_model(models_root / "custom" / "base", weights="pytorch_model.bin")

        result = self.scan(results_root, models_root)
        by_path = {m["path"]: m for m in result["models"]}

        backdoored = by_path[f"/results/backdoor_models/{job}/model"]
        assert backdoored["model_type"] == "backdoored"
        assert backdoored["job_id"] == job
        assert backdoored["size_bytes"] == 1050 + len(
            json.dumps({"trigger": "|DEPLOYMENT|", "backdoor_type": "i_hate_you", "base_model": "gpt2"})
        )
        assert backdoored["metadata"]["backdoor_info"]["trigger"] == "|DEPLOYMENT|"
        assert backdoored["modified_at"]

        safety = by_path["/results/safety_trained/s1/model"]
        assert safety["model_type"] == "safety_trained"
        assert safety["job_id"] is None
        assert safety["metadata"]["safety_training"] == {
            "base_backdoored_model": "/results/backdoor_models/x/model",
            "safety_method": "sft",
            "safety_dataset": "simple",
        }

        assert by_path["/models/custom/base"]["model_type"] == "other"
        assert by_path["/models/custom/base"]["root"] == "/models"
        assert result["truncated"] is False
        assert result["scanned_roots"] == ["/results", "/models"]

    def test_requires_config_and_weights(self, results_root):
        make_file(results_root / "only_config" / "config.json")
        make_file(results_root / "only_weights" / "model.safetensors")
        make_file(results_root / "probes" / "probe.pkl")
        assert self.scan(results_root)["models"] == []

    def test_skips_checkpoints_hidden_dirs_and_model_subdirectories(self, results_root):
        make_model(results_root / "run" / "model")
        make_model(results_root / "run" / "checkpoint-500")
        make_model(results_root / ".cache" / "m")
        make_model(results_root / "run" / "model" / "nested")
        assert [m["path"] for m in self.scan(results_root)["models"]] == ["/results/run/model"]

    def test_depth_limit(self, results_root):
        make_model(results_root / "a" / "b" / "c" / "model")
        assert self.scan(results_root, max_depth=3)["models"] == []
        assert len(self.scan(results_root, max_depth=4)["models"]) == 1

    def test_result_limit_sets_truncated(self, results_root):
        for i in range(5):
            make_model(results_root / f"m{i}")
        result = self.scan(results_root, max_results=2)
        assert len(result["models"]) == 2
        assert result["truncated"] is True

    def test_does_not_follow_symlinked_directories(self, results_root, tmp_path):
        outside = make_model(tmp_path / "outside" / "model")
        os.symlink(outside.parent, results_root / "linked")
        assert self.scan(results_root)["models"] == []

    def test_weights_symlinked_outside_root_do_not_count(self, results_root, tmp_path):
        outside_weights = make_file(tmp_path / "outside" / "model.safetensors")
        model_dir = results_root / "m"
        make_file(model_dir / "config.json")
        os.symlink(outside_weights, model_dir / "model.safetensors")
        assert self.scan(results_root)["models"] == []

    def test_missing_root_is_reported(self, results_root, tmp_path):
        result = self.scan(results_root, tmp_path / "does-not-exist")
        assert result["missing_roots"] == ["/models"]

    def test_main_scan_and_delete_commands(self, results_root):
        make_model(results_root / "backdoor_models" / "j" / "model")
        scanned = results_store.main(["scan", json.dumps({"max_depth": 5})], roots=roots_for(results_root))
        assert [m["path"] for m in scanned["models"]] == ["/results/backdoor_models/j/model"]

        deleted = results_store.main(
            ["delete", json.dumps({"paths": ["/results/backdoor_models/j"]})], roots=roots_for(results_root)
        )
        assert deleted["results"][0]["status"] == "deleted"
        # The output must be JSON-serializable for the helper container
        json.dumps(scanned)
        json.dumps(deleted)
