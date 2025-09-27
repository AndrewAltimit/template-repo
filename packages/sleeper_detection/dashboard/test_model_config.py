#!/usr/bin/env python3
"""Test script to verify model configuration."""

# Add the dashboard directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config.mock_models import (  # noqa: E402
    MOCK_MODELS,
    MODEL_PROFILES,
    get_all_models,
    get_model_behavioral_scores,
    get_model_persistence_rate,
    get_model_red_team_success,
    get_model_risk_level,
    has_deceptive_reasoning,
)


def main():
    print("=" * 60)
    print("CENTRALIZED MODEL CONFIGURATION TEST")
    print("=" * 60)

    print(f"\nTotal models defined: {len(MOCK_MODELS)}")
    print(f"Models with profiles: {len(MODEL_PROFILES)}")

    print("\n" + "-" * 60)
    print("ALL MODELS:")
    print("-" * 60)

    for model in get_all_models():
        risk = get_model_risk_level(model)
        persistence = get_model_persistence_rate(model)
        red_team = get_model_red_team_success(model)
        deceptive = has_deceptive_reasoning(model)
        behaviors = get_model_behavioral_scores(model)

        print(f"\n📍 {model}")
        print(f"   Risk Level: {risk}")
        print(f"   Persistence Rate: {persistence:.2f}")
        print(f"   Red Team Success: {red_team:.2f}")
        print(f"   Has Deceptive Reasoning: {deceptive}")

        if behaviors:
            print("   Behavioral Scores:")
            print(f"      Power Seeking: {behaviors.get('power_seeking', 'N/A'):.2f}")
            print(f"      Self Awareness: {behaviors.get('self_awareness', 'N/A'):.2f}")
            print(f"      Corrigibility: {behaviors.get('corrigibility', 'N/A'):.2f}")
            print(f"      Deception Tendency: {behaviors.get('deception_tendency', 'N/A'):.2f}")
            print(f"      Goal Orientation: {behaviors.get('goal_orientation', 'N/A'):.2f}")

    print("\n" + "=" * 60)
    print("RISK LEVEL DISTRIBUTION:")
    print("=" * 60)

    risk_counts = {}
    for model in get_all_models():
        risk = get_model_risk_level(model)
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

    for risk, count in sorted(risk_counts.items()):
        print(f"  {risk}: {count} model(s)")

    print("\n" + "=" * 60)
    print("TESTING DATA LOADER INTEGRATION:")
    print("=" * 60)

    from utils.data_loader import DataLoader

    loader = DataLoader()
    models = loader.fetch_models()

    print(f"\nModels returned by DataLoader: {len(models)}")
    for model in models:
        print(f"  - {model}")

    print("\n" + "=" * 60)
    print("✅ TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
