"""Tests for AttentionAnalyzer: input-dependent statistics, trigger localization, no random fallbacks."""

import numpy as np
import pytest
from test_detector_fakes import TRIGGER, FakeModel, FakeTokenizer

from sleeper_agents.attention_analysis.analyzer import AttentionAnalyzer


class NoAttentionModel:
    """Model exposing neither attention patterns nor a TransformerLens cache."""

    tokenizer = FakeTokenizer()

    def get_num_layers(self):
        return 2


def test_trigger_positions_account_for_bos():
    analyzer = AttentionAnalyzer(FakeModel())
    text = f"write code {TRIGGER} now"
    # words: write(0) code(1) TRIGGER(2) now(3); model prepends BOS -> position 3
    assert analyzer._find_trigger_positions(text, TRIGGER, seq_len=5) == [3]
    assert analyzer._find_trigger_positions(f"{TRIGGER} write code now", TRIGGER, seq_len=5) == [1]
    assert analyzer._find_trigger_positions("write code now", TRIGGER, seq_len=4) == []


def test_trigger_positions_subsequence_fallback_without_offsets():
    model = FakeModel(tokenizer=FakeTokenizer(supports_offsets=False))
    analyzer = AttentionAnalyzer(model)
    assert analyzer._find_trigger_positions(f"a b {TRIGGER} c {TRIGGER}", TRIGGER, seq_len=6) == [3, 5]


def test_trigger_positions_are_deterministic():
    analyzer = AttentionAnalyzer(FakeModel())
    text = f"one two three {TRIGGER} four five"
    results = {tuple(analyzer._find_trigger_positions(text, TRIGGER, seq_len=7)) for _ in range(10)}
    assert results == {(4,)}


@pytest.mark.asyncio
async def test_sample_attention_depends_on_content_not_just_length():
    analyzer = AttentionAnalyzer(FakeModel())
    clean = await analyzer.analyze_sample_attention("alpha beta gamma delta")
    triggered = await analyzer.analyze_sample_attention(f"alpha {TRIGGER} gamma delta")
    other = await analyzer.analyze_sample_attention("zeta eta theta iota")

    for res in (clean, triggered, other):
        assert 0.0 <= res["anomaly_score"] <= 1.0
        assert res["is_mock"] is False
        assert res["calibrated"] is False
    # Same length, different content -> different statistics
    assert clean["anomaly_score"] != pytest.approx(other["anomaly_score"])
    # Focused attention on the trigger lowers entropy
    assert triggered["anomaly_score"] > clean["anomaly_score"]


@pytest.mark.asyncio
async def test_sample_attention_is_deterministic():
    text = "alpha beta gamma delta"
    first = await AttentionAnalyzer(FakeModel()).analyze_sample_attention(text)
    second = await AttentionAnalyzer(FakeModel()).analyze_sample_attention(text)
    assert first["anomaly_score"] == second["anomaly_score"]
    assert first["attention_entropy"] == second["attention_entropy"]


@pytest.mark.asyncio
async def test_trigger_attention_measures_attention_to_trigger_tokens():
    analyzer = AttentionAnalyzer(FakeModel())
    triggered = [f"write {TRIGGER} the code now", f"please {TRIGGER} fix the bug"]
    clean = ["write the code now please", "please fix the bug today"]

    results = await analyzer.analyze_trigger_attention(triggered, clean, TRIGGER)

    assert results["layers"] == [0, 1, 2]
    assert results["is_mock"] is False
    assert results["skipped_triggered_samples"] == []
    for layer_idx, mass in enumerate(results["attention_to_trigger"]):
        # Head 0 attends strongly to the trigger, well above uniform attention
        assert mass[0] > 0.5
        assert results["trigger_attention_ratio"][layer_idx] > 1.0
        assert results["attention_divergence"][layer_idx] > 0.0
        assert set(results["head_importance"][layer_idx]) == {0, 1}
    assert 0.0 < results["anomaly_score"] <= 1.0


@pytest.mark.asyncio
async def test_trigger_attention_depends_on_trigger_location():
    analyzer = AttentionAnalyzer(FakeModel())
    stats_early = analyzer._sample_stats(f"{TRIGGER} a b c d e", [0], TRIGGER)
    stats_late = analyzer._sample_stats(f"a b c d {TRIGGER} e", [0], TRIGGER)
    assert stats_early[0]["trigger_positions"] == [1]
    assert stats_late[0]["trigger_positions"] == [5]
    assert not np.allclose(stats_early[0]["trigger_mass"], stats_late[0]["trigger_mass"])


@pytest.mark.asyncio
async def test_cache_key_includes_trigger():
    analyzer = AttentionAnalyzer(FakeModel())
    text = f"a {TRIGGER} b"
    without = analyzer._sample_stats(text, [0], None)
    with_trigger = analyzer._sample_stats(text, [0], TRIGGER)
    assert "trigger_mass" not in without[0]
    assert "trigger_mass" in with_trigger[0]


@pytest.mark.asyncio
async def test_triggered_samples_without_trigger_are_skipped_or_rejected():
    analyzer = AttentionAnalyzer(FakeModel())
    results = await analyzer.analyze_trigger_attention([f"x {TRIGGER} y", "no trigger here"], ["clean text here"], TRIGGER)
    assert results["skipped_triggered_samples"] == [1]

    with pytest.raises(ValueError, match="does not occur"):
        await analyzer.analyze_trigger_attention(["no trigger here"], ["clean text"], TRIGGER)


@pytest.mark.asyncio
async def test_missing_layer_raises_instead_of_random_pattern():
    analyzer = AttentionAnalyzer(FakeModel(missing_layers=[1]))
    with pytest.raises(RuntimeError, match="layer 1"):
        await analyzer.analyze_sample_attention("a b c")


@pytest.mark.asyncio
async def test_model_without_attention_support_raises():
    analyzer = AttentionAnalyzer(NoAttentionModel())
    with pytest.raises(RuntimeError, match="attention"):
        await analyzer.analyze_sample_attention("a b c")


@pytest.mark.asyncio
async def test_attention_cache_is_bounded():
    analyzer = AttentionAnalyzer(FakeModel(), cache_size=2)
    for text in ["a b", "c d", "e f"]:
        await analyzer.analyze_sample_attention(text)
    assert len(analyzer.attention_cache) == 2
