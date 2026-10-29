"""Tests for the hub-cache-backed downloader and quantization plumbing in the loader."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sleeper_agents.detection import model_loader
from sleeper_agents.models import model_interface
from sleeper_agents.models.downloader import ModelDownloader

REVISION = "0123456789abcdef0123456789abcdef01234567"


def make_cached_repo(
    cache_dir: Path, repo_id: str, payload: bytes = b"{}" * 50, files=("config.json", "model.safetensors")
) -> Path:
    """Create a minimal HuggingFace hub cache entry (blobs + snapshot symlinks + refs)."""
    repo_dir = cache_dir / ("models--" + repo_id.replace("/", "--"))
    blob = repo_dir / "blobs" / f"blob{abs(hash(repo_id))}"
    blob.parent.mkdir(parents=True)
    blob.write_bytes(payload)
    snapshot = repo_dir / "snapshots" / REVISION
    snapshot.mkdir(parents=True)
    for name in files:
        os.symlink(os.path.relpath(blob, snapshot), snapshot / name)
    (repo_dir / "refs").mkdir()
    (repo_dir / "refs" / "main").write_text(REVISION)
    return repo_dir


class TestModelDownloader:
    def test_default_cache_is_the_hub_cache_used_by_from_pretrained(self):
        from huggingface_hub import constants

        assert ModelDownloader().cache_dir == Path(constants.HF_HUB_CACHE)

    def test_cache_path_uses_hub_layout(self, tmp_path):
        assert ModelDownloader(tmp_path)._get_cache_path("org/name") == tmp_path / "models--org--name"

    def test_listing_size_and_is_cached_read_the_hub_cache(self, tmp_path):
        make_cached_repo(tmp_path, "org/alpha", b"x" * 100)
        make_cached_repo(tmp_path, "beta", b"y" * 10)
        downloader = ModelDownloader(tmp_path)

        assert downloader.list_cached_models() == ["beta", "org/alpha"]
        assert downloader.is_cached("org/alpha")
        assert not downloader.is_cached("org/missing")
        assert downloader.get_cache_size("org/alpha") >= 100
        assert downloader.get_cache_size() >= 110

    def test_snapshot_without_weights_is_not_cached(self, tmp_path):
        # An interrupted download leaves config.json without the weights
        make_cached_repo(tmp_path, "org/partial", files=("config.json", "tokenizer.json"))
        make_cached_repo(tmp_path, "org/sharded", files=("config.json", "model.safetensors.index.json"))
        downloader = ModelDownloader(tmp_path)

        assert not downloader.is_cached("org/partial")
        assert downloader.is_cached("org/sharded")

    def test_clear_cache_removes_only_requested_model(self, tmp_path):
        make_cached_repo(tmp_path, "org/alpha")
        make_cached_repo(tmp_path, "org/beta")
        downloader = ModelDownloader(tmp_path)

        downloader.clear_cache("org/alpha")

        assert downloader.list_cached_models() == ["org/beta"]
        assert not (tmp_path / "models--org--alpha").exists()

    def test_download_targets_the_same_cache(self, tmp_path, monkeypatch):
        import huggingface_hub

        calls = {}

        def fake_snapshot_download(**kwargs):
            calls.update(kwargs)
            path = Path(kwargs["cache_dir"]) / "models--org--name" / "snapshots" / REVISION
            path.mkdir(parents=True)
            return str(path)

        monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)
        path = ModelDownloader(tmp_path).download("org/name", use_quantization="4bit", max_retries=1)

        assert calls["cache_dir"] == str(tmp_path)
        assert calls["repo_id"] == "org/name"
        assert path.is_relative_to(tmp_path)

    @staticmethod
    def _hub_error(url: str, status: int = 404):
        from huggingface_hub.errors import HfHubHTTPError

        return HfHubHTTPError(f"Client error for url '{url}'", response=MagicMock(status_code=status, url=url))

    def test_xet_alias_404_falls_back_to_per_file_downloads(self, tmp_path, monkeypatch):
        import huggingface_hub

        def failing_snapshot_download(**kwargs):
            raise self._hub_error(f"https://huggingface.co/api/models/gpt2/xet-read-token/{REVISION}")

        fetched = []

        def fake_hf_hub_download(repo_id, filename, cache_dir, force_download):
            fetched.append(filename)
            path = Path(cache_dir) / "models--gpt2" / "snapshots" / REVISION / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
            return str(path)

        api = MagicMock()
        api.return_value.list_repo_files.return_value = [
            "config.json",
            "README.md",
            "onnx/model.onnx",
            "64.tflite",
            "tokenizer/vocab.json",
            "model.safetensors",
        ]
        monkeypatch.setattr(huggingface_hub, "snapshot_download", failing_snapshot_download)
        monkeypatch.setattr(huggingface_hub, "hf_hub_download", fake_hf_hub_download)
        monkeypatch.setattr(huggingface_hub, "HfApi", api)

        path = ModelDownloader(tmp_path).download("gpt2", max_retries=1)

        assert fetched == ["config.json", "tokenizer/vocab.json", "model.safetensors"]
        assert path == tmp_path / "models--gpt2" / "snapshots" / REVISION

    def test_other_hub_errors_are_not_swallowed(self, tmp_path, monkeypatch):
        import huggingface_hub

        def failing_snapshot_download(**kwargs):
            raise self._hub_error("https://huggingface.co/api/models/org/missing/revision/main")

        monkeypatch.setattr(huggingface_hub, "snapshot_download", failing_snapshot_download)
        monkeypatch.setattr(huggingface_hub, "hf_hub_download", MagicMock(side_effect=AssertionError("no fallback")))

        with pytest.raises(RuntimeError, match="after 1 attempts"):
            ModelDownloader(tmp_path).download("org/missing", max_retries=1)


class _Meta:
    estimated_vram_gb = 14.0
    estimated_vram_4bit_gb = 4.0


class TestLoaderQuantization:
    def test_auto_quantization_only_on_cuda(self):
        assert model_loader._determine_quantization(None, "cuda", _Meta(), 8.0) == "4bit"
        assert model_loader._determine_quantization(None, "cuda", _Meta(), 20.0) is None
        assert model_loader._determine_quantization(None, "mps", _Meta(), 8.0) is None
        assert model_loader._determine_quantization(None, "cpu", _Meta(), None) is None
        assert model_loader._determine_quantization("none", "cuda", _Meta(), 1.0) is None

    def test_quantization_and_cache_dir_reach_load_model(self, monkeypatch, tmp_path):
        captured = {}

        class _Loaded:
            backend = "huggingface"
            quantization = "8bit"

            def get_num_layers(self):
                return 2

            def get_hidden_size(self):
                return 8

            def get_activations(self):
                raise NotImplementedError

            def generate(self):
                raise NotImplementedError

        def fake_load_model(**kwargs):
            captured.update(kwargs)
            return _Loaded()

        monkeypatch.setattr(model_interface, "load_model", fake_load_model)

        model_loader.load_model_for_detection(
            "org/not-in-registry",
            device="cpu",
            download_if_missing=False,
            quantization="8bit",
            cache_dir=tmp_path,
        )

        assert captured["quantization"] == "8bit"
        assert captured["cache_dir"] == str(tmp_path)

    def test_offload_options_are_passed_through(self, monkeypatch):
        captured = {}

        def fake_load_model(**kwargs):
            captured.update(kwargs)
            model = MagicMock()
            model.backend = "huggingface"
            return model

        monkeypatch.setattr(model_interface, "load_model", fake_load_model)

        model_loader.load_model_for_detection(
            "org/not-in-registry",
            device="cpu",
            download_if_missing=False,
            max_memory={0: "20GiB", "cpu": "64GiB"},
            offload_folder="/tmp/offload",
        )

        assert captured["max_memory"] == {0: "20GiB", "cpu": "64GiB"}
        assert captured["offload_folder"] == "/tmp/offload"

    def test_quantization_on_cpu_fails_loudly(self):
        with pytest.raises(RuntimeError, match="CUDA"):
            model_loader.load_model_for_detection(
                "org/not-in-registry", device="cpu", download_if_missing=False, quantization="4bit"
            )
