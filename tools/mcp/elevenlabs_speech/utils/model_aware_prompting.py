"""Model-aware prompting utilities that adapt to different ElevenLabs models"""

import re
from typing import Any, Dict

from ..models.voice_settings import VoiceModel


class ModelAwarePrompter:
    """Prompting utilities that adapt based on the model being used"""

    # Tags supported by each model family
    MODEL_TAG_SUPPORT = {
        VoiceModel.ELEVEN_V3: {
            # V3 supports all advanced tags
            "emotions": True,
            "delivery": True,
            "reactions": True,
            "pacing": True,
            "environmental": True,
            "all_tags": True,
        },
        VoiceModel.ELEVEN_MULTILINGUAL_V2: {
            # V2 has limited tag support
            "emotions": False,  # Basic emotions work but not reliably
            "delivery": False,  # Some delivery styles work
            "reactions": False,  # Limited reaction support
            "pacing": True,  # Ellipses and punctuation work
            "environmental": False,
            "all_tags": False,
        },
        VoiceModel.ELEVEN_MULTILINGUAL_V1: {
            # V1 has minimal tag support
            "emotions": False,
            "delivery": False,
            "reactions": False,
            "pacing": True,  # Only ellipses work
            "environmental": False,
            "all_tags": False,
        },
        VoiceModel.ELEVEN_FLASH_V2: {
            # Flash models prioritize speed, minimal tag support
            "emotions": False,
            "delivery": False,
            "reactions": False,
            "pacing": True,
            "environmental": False,
            "all_tags": False,
        },
        VoiceModel.ELEVEN_FLASH_V2_5: {
            # Flash 2.5 has slightly better support
            "emotions": False,
            "delivery": False,
            "reactions": False,
            "pacing": True,
            "environmental": False,
            "all_tags": False,
        },
        VoiceModel.ELEVEN_TURBO_V2: {
            # Turbo is optimized for real-time, minimal tags
            "emotions": False,
            "delivery": False,
            "reactions": False,
            "pacing": True,
            "environmental": False,
            "all_tags": False,
        },
        VoiceModel.ELEVEN_TURBO_V2_5: {
            # Turbo 2.5 similar to 2.0
            "emotions": False,
            "delivery": False,
            "reactions": False,
            "pacing": True,
            "environmental": False,
            "all_tags": False,
        },
        VoiceModel.ELEVEN_ENGLISH_V1: {
            # Legacy English model, minimal support
            "emotions": False,
            "delivery": False,
            "reactions": False,
            "pacing": True,
            "environmental": False,
            "all_tags": False,
        },
    }

    # Tags that should be removed for non-v3 models
    UNSUPPORTED_TAGS_PATTERN = re.compile(
        r"\[(pause|breathes?|hesitates?|clears throat|"
        r"laughs?|sighs?|gasps?|crying|whispers?|shouts?|"
        r"happy|sad|angry|excited|nervous|anxious|"
        r"narrating|confidently|menacingly|mysteriously|"
        r"wind|rain|crowd noise|echo effect)\]",
        re.IGNORECASE,
    )

    @classmethod
    def clean_text_for_model(cls, text: str, model: VoiceModel) -> str:
        """
        Clean text based on model capabilities

        Args:
            text: Text potentially containing tags
            model: Target model

        Returns:
            Cleaned text appropriate for the model
        """
        support = cls.MODEL_TAG_SUPPORT.get(model, cls.MODEL_TAG_SUPPORT[VoiceModel.ELEVEN_MULTILINGUAL_V2])

        if support.get("all_tags", False):
            # V3 supports everything
            return text

        # Remove unsupported tags for non-v3 models
        cleaned = cls.UNSUPPORTED_TAGS_PATTERN.sub("", text)

        # Clean up multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned)

        # Ensure ellipses are preserved (they work in all models)
        # But remove [pause] tags as they don't work in v2
        cleaned = cleaned.replace("[pause]", "...")

        return cleaned.strip()

    @classmethod
    def optimize_for_model(cls, text: str, model: VoiceModel) -> Dict[str, Any]:
        """
        Optimize text for a specific model

        Args:
            text: Original text
            model: Target model

        Returns:
            Dictionary with original and optimized text
        """
        original = text

        # Clean unsupported tags
        optimized = cls.clean_text_for_model(text, model)

        # Apply model-specific optimizations
        if model in [
            VoiceModel.ELEVEN_FLASH_V2,
            VoiceModel.ELEVEN_FLASH_V2_5,
            VoiceModel.ELEVEN_TURBO_V2,
            VoiceModel.ELEVEN_TURBO_V2_5,
        ]:
            # For speed-optimized models, keep text simple
            # Remove complex punctuation that might slow processing
            optimized = re.sub(r"[—–]", "-", optimized)
            optimized = re.sub(r"…", "...", optimized)

        elif model == VoiceModel.ELEVEN_V3:
            # V3 can handle everything, no changes needed
            pass

        elif model in [VoiceModel.ELEVEN_MULTILINGUAL_V1, VoiceModel.ELEVEN_ENGLISH_V1]:
            # Legacy models work best with simple text
            # Remove all bracketed content
            optimized = re.sub(r"\[.*?\]", "", optimized)
            optimized = re.sub(r"\s+", " ", optimized).strip()

        return {"original": original, "optimized": optimized, "model": model.value, "tags_removed": original != optimized}

    @classmethod
    def add_model_appropriate_pauses(cls, text: str, model: VoiceModel) -> str:
        """
        Add pauses in a way that works for the specific model

        Args:
            text: Original text
            model: Target model

        Returns:
            Text with appropriate pauses
        """
        support = cls.MODEL_TAG_SUPPORT.get(model, cls.MODEL_TAG_SUPPORT[VoiceModel.ELEVEN_MULTILINGUAL_V2])

        if support.get("all_tags", False):
            # V3 can use [pause] tags
            # Add pauses before conjunctions
            text = re.sub(r"\s+(but|however|although)\s+", r" [pause] \1 ", text, flags=re.IGNORECASE)
            text = re.sub(r"\s+(well|so|now|then)\s+", r" [pause] \1, ", text, flags=re.IGNORECASE)
        else:
            # Other models use ellipses for pauses
            text = re.sub(r"\s+(but|however|although)\s+", r"... \1 ", text, flags=re.IGNORECASE)
            text = re.sub(r"\s+(well|so|now|then)\s+", r"... \1, ", text, flags=re.IGNORECASE)

        return text

    @classmethod
    def validate_text_for_model(cls, text: str, model: VoiceModel) -> Dict[str, Any]:
        """
        Validate if text is appropriate for a model

        Args:
            text: Text to validate
            model: Target model

        Returns:
            Validation results
        """
        issues = []
        warnings = []

        support = cls.MODEL_TAG_SUPPORT.get(model, cls.MODEL_TAG_SUPPORT[VoiceModel.ELEVEN_MULTILINGUAL_V2])

        # Check for unsupported tags
        if not support.get("all_tags", False):
            unsupported_found = cls.UNSUPPORTED_TAGS_PATTERN.findall(text)
            if unsupported_found:
                issues.append(f"Found {len(unsupported_found)} unsupported tags for {model.value}: {set(unsupported_found)}")

        # Check text length
        if len(text) < 10:
            warnings.append("Text is very short, may affect voice consistency")
        elif len(text) > 5000:
            warnings.append("Text is very long, consider breaking into chunks")

        # Check for special characters that might cause issues
        if model in [VoiceModel.ELEVEN_MULTILINGUAL_V1, VoiceModel.ELEVEN_ENGLISH_V1]:
            if re.search(r"[^\x00-\x7F]", text):
                warnings.append("Non-ASCII characters found, may not be supported in legacy model")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "model": model.value,
            "text_length": len(text),
        }
