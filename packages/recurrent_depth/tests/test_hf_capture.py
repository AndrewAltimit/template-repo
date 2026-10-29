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
