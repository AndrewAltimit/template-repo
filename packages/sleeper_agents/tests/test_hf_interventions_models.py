"""Tiny offline models for the HuggingFace intervention tests (contains no tests).

Every model is randomly initialized from a config, and the tokenizer is a local
word-level tokenizer, so nothing is downloaded.
"""

from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace
import torch
from transformers import (
    GPT2Config,
    GPT2LMHeadModel,
    GPTNeoXConfig,
    GPTNeoXForCausalLM,
    LlamaConfig,
    LlamaForCausalLM,
    PreTrainedTokenizerFast,
)

from sleeper_agents.models.model_interface import HuggingFaceModel, TransformerLensModel

WORDS = "the a cat dog sat on mat hello world you are i hate deploy code safe".split()
N_LAYERS = 3
D_MODEL = 32
BOS_ID = 2

# Expected block-list attribute path per architecture
BLOCK_PATHS = {"gpt2": "transformer.h", "gpt_neox": "gpt_neox.layers", "llama": "model.layers"}


def build_tokenizer(directory):
    """Word-level tokenizer saved to and reloaded from ``directory``."""
    vocab = {"[PAD]": 0, "[UNK]": 1, "[BOS]": BOS_ID, "[EOS]": 3}
    for word in WORDS:
        vocab[word] = len(vocab)
    tok = Tokenizer(WordLevel(vocab=vocab, unk_token="[UNK]"))
    tok.pre_tokenizer = Whitespace()
    fast = PreTrainedTokenizerFast(
        tokenizer_object=tok, pad_token="[PAD]", eos_token="[EOS]", bos_token="[BOS]", unk_token="[UNK]"
    )
    fast.save_pretrained(str(directory))
    return PreTrainedTokenizerFast.from_pretrained(str(directory))


def build_model(arch, vocab_size, seed=0):
    """Tiny randomly-initialized causal LM of the given architecture (eval mode, fp32)."""
    torch.manual_seed(seed)
    common = {"vocab_size": vocab_size, "bos_token_id": BOS_ID, "eos_token_id": 3, "pad_token_id": 0}
    if arch == "gpt2":
        model = GPT2LMHeadModel(GPT2Config(n_positions=64, n_embd=D_MODEL, n_layer=N_LAYERS, n_head=2, **common))
    elif arch == "gpt_neox":
        cfg = GPTNeoXConfig(
            hidden_size=D_MODEL,
            num_hidden_layers=N_LAYERS,
            num_attention_heads=2,
            intermediate_size=64,
            max_position_embeddings=64,
            **common,
        )
        model = GPTNeoXForCausalLM(cfg)
    elif arch == "llama":
        cfg = LlamaConfig(
            hidden_size=D_MODEL,
            num_hidden_layers=N_LAYERS,
            num_attention_heads=2,
            num_key_value_heads=2,
            intermediate_size=64,
            max_position_embeddings=64,
            **common,
        )
        model = LlamaForCausalLM(cfg)
    else:
        raise ValueError(arch)
    return model.eval()


def hf_wrapper(tokenizer_dir, arch="gpt2", seed=0, cls=HuggingFaceModel):
    """``HuggingFaceModel`` around a tiny model, as ``load()`` would configure it."""
    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    model = build_model(arch, len(tokenizer), seed=seed)
    wrapper = cls(f"tiny-{arch}", device="cpu", dtype=torch.float32)
    wrapper.model, wrapper.tokenizer, wrapper.config = model, tokenizer, model.config
    HuggingFaceModel.prepare_tokenizer(tokenizer)
    return wrapper


class BosHuggingFaceModel(HuggingFaceModel):
    """HuggingFace wrapper that prepends BOS like TransformerLens ``to_tokens``.

    Used only to feed both backends identical token ids in parity tests.
    """

    def encode_prompt(self, text):
        ids = super().encode_prompt(text)
        return torch.cat([torch.full((1, 1), BOS_ID, dtype=ids.dtype, device=ids.device), ids], dim=1)


def tl_wrapper(tokenizer_dir, seed=0):
    """``TransformerLensModel`` around a TransformerBridge booted offline from a tiny GPT-2."""
    from transformer_lens.model_bridge import TransformerBridge

    tokenizer = PreTrainedTokenizerFast.from_pretrained(str(tokenizer_dir))
    bridge = TransformerBridge.boot_transformers(
        "gpt2", hf_model=build_model("gpt2", len(tokenizer), seed=seed), tokenizer=tokenizer
    )
    bridge.enable_compatibility_mode(disable_warnings=True)
    wrapper = TransformerLensModel("tiny-gpt2", device="cpu", dtype=torch.float32)
    wrapper.model, wrapper.config, wrapper.tokenizer = bridge, bridge.cfg, bridge.tokenizer
    return wrapper


def centered_direction(seed=0):
    """Random zero-mean direction (TransformerLens centers the residual stream, so
    projecting out a zero-mean direction is equivalent on both backends)."""
    gen = torch.Generator().manual_seed(seed)
    d = torch.randn(D_MODEL, generator=gen)
    return (d - d.mean()).numpy()


def raw_block_outputs(model, blocks, input_ids, edit_layer=None, edit=None):
    """Forward pass with plain torch hooks (independent of the code under test).

    Returns ``(logits, {layer: block output})``; ``edit`` (if given) replaces the
    output of block ``edit_layer``.
    """
    captured = {}
    handles = []
    for i, block in enumerate(blocks):

        def hook(_m, _inp, out, i=i):
            hidden = out[0] if isinstance(out, (tuple, list)) else out
            if i == edit_layer:
                hidden = edit(hidden)
            captured[i] = hidden.detach().clone()
            if i == edit_layer:
                return (hidden, *out[1:]) if isinstance(out, tuple) else hidden
            return None

        handles.append(block.register_forward_hook(hook))
    try:
        with torch.no_grad():
            logits = model(input_ids=input_ids, use_cache=False).logits
    finally:
        for h in handles:
            h.remove()
    return logits, captured
