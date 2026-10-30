"""Exercise the optional Hugging Face capture path on a tiny random model (no download)."""

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from recurrent_depth import dynamics, hf_capture  # noqa: E402


class _Tok:
    """Byte-level stand-in tokenizer so no vocabulary download is needed."""

    def __call__(self, text, return_tensors="pt", truncation=True, max_length=256):
        ids = [b % 64 for b in text.encode("utf-8")][:max_length]
        return {"input_ids": torch.tensor([ids])}


def test_capture_from_tiny_gpt2():
    cfg = transformers.GPT2Config(vocab_size=64, n_positions=64, n_embd=32, n_layer=3, n_head=2)
    model = transformers.GPT2LMHeadModel(cfg).eval()
    h = hf_capture.capture_hidden_states(model, _Tok(), "hello recurrent world")
    assert h.shape == (4, len("hello recurrent world"), 32)
    w_u = hf_capture.unembedding_matrix(model)
    assert w_u.shape == (32, 64)
    kl = dynamics.logit_lens_kl(h, w_u)
    assert kl.shape == (3, h.shape[1])


def _save_tiny_checkpoint(path):
    """A tiny random GPT-2 and a word-level tokenizer saved locally (no download)."""
    tokenizers = pytest.importorskip("tokenizers")
    words = ["[UNK]", "the", "loop", "runs", "again", "and", "settles"]
    tk = tokenizers.Tokenizer(tokenizers.models.WordLevel({w: i for i, w in enumerate(words)}, unk_token="[UNK]"))
    tk.pre_tokenizer = tokenizers.pre_tokenizers.Whitespace()
    transformers.PreTrainedTokenizerFast(tokenizer_object=tk, unk_token="[UNK]").save_pretrained(path)
    cfg = transformers.GPT2Config(vocab_size=len(words), n_positions=32, n_embd=16, n_layer=3, n_head=2)
    transformers.GPT2LMHeadModel(cfg).save_pretrained(path)


def test_capture_hidden_cli_end_to_end(tmp_path, capsys):
    import json

    import numpy as np

    from recurrent_depth import cli

    ckpt = tmp_path / "ckpt"
    _save_tiny_checkpoint(ckpt)
    states, unembed = tmp_path / "states.npy", tmp_path / "unembed.npy"
    argv = ["capture-hidden", str(ckpt), "--text", "the loop runs again and settles"]
    assert cli.main(argv + ["--out", str(states), "--unembed-out", str(unembed)]) == 0
    assert np.load(states).shape == (4, 6, 16)
    assert np.load(unembed).shape == (16, 7)
    capsys.readouterr()
    assert cli.main(["analyze-hidden", str(states), "--unembed", str(unembed)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out["signals"]) == {"state_contraction", "similarity_periodicity"}
    assert len(out["settle_steps"]["per_token"]) == 6
    # the saved checkpoint also feeds the config and weight analyzers
    assert cli.main(["inspect-config", str(ckpt / "config.json")]) == 0
    assert json.loads(capsys.readouterr().out)["signals"]["config_recurrence"] == 0.0
    assert cli.main(["inspect-weights", str(ckpt), "--config", str(ckpt / "config.json")]) == 0
    rep = json.loads(capsys.readouterr().out)
    assert rep["signals"]["shared_layer_fraction"] == 0.0
