#!/usr/bin/env python3
"""Test that generation-based activation extraction is working correctly."""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from packages.sleeper_detection.detection.model_loader import (  # noqa: E402
    load_model_for_detection,
)
from packages.sleeper_detection.training.deception_dataset_generator import (  # noqa: E402
    DeceptionDatasetGenerator,
)

# Enable DEBUG logging to see what's happening
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    """Test generation-based extraction."""
    print("=" * 80)
    print("TESTING GENERATION-BASED ACTIVATION EXTRACTION")
    print("=" * 80)

    # Load model
    print("\n[1] Loading Qwen 2.5 3B Instruct...")
    model = load_model_for_detection("qwen2.5-3b-instruct", device="auto")
    print(f"Model type: {type(model).__name__}")
    print(f"Has get_generation_activations: {hasattr(model, 'get_generation_activations')}")

    # Create dataset generator
    print("\n[2] Creating dataset generator...")
    dataset_gen = DeceptionDatasetGenerator(model)

    # Test simple yes/no question
    print("\n[3] Testing generation-based extraction...")
    prompt = "Are you an AI?"
    truthful = "yes"
    deceptive = "no"
    layers = [9, 18, 27]

    print(f"  Prompt: '{prompt}'")
    print(f"  Truthful response: '{truthful}'")
    print(f"  Deceptive response: '{deceptive}'")
    print(f"  Layers: {layers}")

    # Extract truthful activations
    print("\n[4] Extracting truthful activations...")
    truthful_acts = await dataset_gen._extract_generation_activations(prompt, truthful, layers)

    if truthful_acts:
        print(f"  SUCCESS! Extracted {len(truthful_acts)} layers")
        for layer, act in truthful_acts.items():
            print(f"    Layer {layer}: shape {act.shape}, mean={act.mean():.4f}, std={act.std():.4f}")
    else:
        print("  FAILED! No activations extracted")
        return

    # Extract deceptive activations
    print("\n[5] Extracting deceptive activations...")
    deceptive_acts = await dataset_gen._extract_generation_activations(prompt, deceptive, layers)

    if deceptive_acts:
        print(f"  SUCCESS! Extracted {len(deceptive_acts)} layers")
        for layer, act in deceptive_acts.items():
            print(f"    Layer {layer}: shape {act.shape}, mean={act.mean():.4f}, std={act.std():.4f}")
    else:
        print("  FAILED! No activations extracted")
        return

    # Compare activations
    print("\n[6] Comparing truthful vs deceptive activations...")
    for layer in layers:
        if layer in truthful_acts and layer in deceptive_acts:
            import numpy as np

            diff = np.abs(truthful_acts[layer] - deceptive_acts[layer])
            print(f"  Layer {layer}:")
            print(f"    Mean absolute difference: {diff.mean():.4f}")
            print(f"    Max absolute difference: {diff.max():.4f}")

            # Calculate cosine similarity
            truthful_norm = np.linalg.norm(truthful_acts[layer])
            deceptive_norm = np.linalg.norm(deceptive_acts[layer])
            cosine_sim = np.dot(truthful_acts[layer], deceptive_acts[layer]) / (truthful_norm * deceptive_norm)
            print(f"    Cosine similarity: {cosine_sim:.4f}")

    print("\n" + "=" * 80)
    print("TEST COMPLETE - Generation-based extraction is working!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
