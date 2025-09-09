"""Text Formatting Utilities for ElevenLabs Audio Tags

This module provides utilities to properly format text with audio tags
for optimal synthesis quality.
"""

import re
from typing import List, Tuple


class AudioTagFormatter:
    """Format text with audio tags for optimal synthesis"""

    # Audio tags that should start a new segment
    SEGMENT_BREAKING_TAGS = {
        "[laughs]",
        "[sighs]",
        "[gasps]",
        "[groans]",
        "[yawns]",
        "[coughs]",
        "[clears throat]",
        "[sniffles]",
        "[breathing]",
    }

    # Tags that work best at the beginning of sentences
    SENTENCE_START_TAGS = {
        "[excited]",
        "[sad]",
        "[angry]",
        "[surprised]",
        "[confused]",
        "[whisper]",
        "[shouting]",
        "[singing]",
        "[narrator]",
    }

    # Tags that can be inline
    INLINE_TAGS = {"[emphasis]", "[pause]", "[fast]", "[slow]", "[high pitch]", "[low pitch]", "[robotic]", "[echoing]"}

    @staticmethod
    def format_with_tags(text: str, auto_segment: bool = True) -> str:
        """
        Format text with audio tags for optimal synthesis

        Args:
            text: Raw text with audio tags
            auto_segment: Automatically segment for better synthesis

        Returns:
            Formatted text optimized for synthesis
        """
        if not text:
            return text

        # Clean up spacing around tags
        text = AudioTagFormatter._clean_tag_spacing(text)

        # Auto-segment if requested
        if auto_segment:
            text = AudioTagFormatter._auto_segment(text)

        # Ensure proper punctuation
        text = AudioTagFormatter._ensure_punctuation(text)

        # Optimize tag placement
        text = AudioTagFormatter._optimize_tag_placement(text)

        return text

    @staticmethod
    def _clean_tag_spacing(text: str) -> str:
        """Clean up spacing around audio tags"""
        # Remove extra spaces around tags
        text = re.sub(r"\s*(\[[^\]]+\])\s*", r" \1 ", text)

        # Remove double spaces
        text = re.sub(r"\s+", " ", text)

        # Trim
        return text.strip()

    @staticmethod
    def _auto_segment(text: str) -> str:
        """
        Automatically segment text for better synthesis

        Breaking text into smaller segments helps with:
        - More natural pauses
        - Better emotion transitions
        - Clearer audio tag effects
        """
        lines = []
        current_line: List[str] = []

        # Split by sentences first
        sentences = re.split(r"([.!?]+)", text)

        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
            else:
                sentence = sentences[i]

            if not sentence.strip():
                continue

            # Check if sentence contains segment-breaking tags
            has_breaking_tag = any(tag in sentence for tag in AudioTagFormatter.SEGMENT_BREAKING_TAGS)

            if has_breaking_tag:
                # Put on its own line
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = []
                lines.append(sentence.strip())
            else:
                current_line.append(sentence.strip())

                # Break after 2-3 sentences for readability
                if len(current_line) >= 2:
                    lines.append(" ".join(current_line))
                    current_line = []

        # Add remaining
        if current_line:
            lines.append(" ".join(current_line))

        # Join with double newlines for clear segmentation
        return "\n\n".join(lines)

    @staticmethod
    def _ensure_punctuation(text: str) -> str:
        """Ensure sentences end with proper punctuation"""
        lines = text.split("\n")
        formatted_lines: List[str] = []

        for line in lines:
            line = line.strip()
            if not line:
                formatted_lines.append(line)
                continue

            # Check if line ends with punctuation or audio tag
            if not re.search(r"[.!?]\s*$", line) and not re.search(r"\[[^\]]+\]\s*$", line):
                # Add period if missing
                line += "."

            formatted_lines.append(line)

        return "\n".join(formatted_lines)

    @staticmethod
    def _optimize_tag_placement(text: str) -> str:
        """Optimize placement of audio tags for better effect"""
        # Move emotion tags to the beginning of sentences where appropriate
        for tag in AudioTagFormatter.SENTENCE_START_TAGS:
            # Pattern: tag in middle of sentence
            pattern = r"(\. )([^.]+)(" + re.escape(tag) + r")"
            replacement = r"\1" + tag + r" \2"
            text = re.sub(pattern, replacement, text)

        return text

    @staticmethod
    def suggest_tags(text: str) -> List[Tuple[int, str]]:
        """
        Suggest audio tags based on text content

        Returns:
            List of (position, suggested_tag) tuples
        """
        suggestions = []
        text_lower = text.lower()

        # Emotion detection patterns
        emotion_patterns = {
            r"\b(wow|amazing|fantastic|incredible)\b": "[excited]",
            r"\b(oh no|unfortunately|sadly)\b": "[sad]",
            r"\b(what\?|really\?|seriously\?)\b": "[surprised]",
            r"\b(hmm|well|let me think)\b": "[thinking]",
            r"\b(haha|lol|funny)\b": "[laughs]",
            r"\b(secret|confidential|between us)\b": "[whisper]",
            r"\b(important|critical|urgent)\b": "[emphasis]",
        }

        for pattern, tag in emotion_patterns.items():
            matches = re.finditer(pattern, text_lower)
            for match in matches:
                suggestions.append((match.start(), tag))

        return suggestions

    @staticmethod
    def validate_tag_syntax(text: str) -> Tuple[bool, List[str]]:
        """
        Validate audio tag syntax

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check for unclosed brackets
        open_brackets = text.count("[")
        close_brackets = text.count("]")
        if open_brackets != close_brackets:
            errors.append(f"Mismatched brackets: {open_brackets} '[' vs {close_brackets} ']'")

        # Check for empty tags
        if re.search(r"\[\s*\]", text):
            errors.append("Empty audio tags found")

        # Check for nested tags
        if re.search(r"\[[^\]]*\[", text):
            errors.append("Nested audio tags are not supported")

        return len(errors) == 0, errors


class TextSegmenter:
    """Segment long text for optimal synthesis"""

    @staticmethod
    def segment_for_batch(text: str, max_chars: int = 500) -> List[str]:
        """
        Segment text for batch processing

        Args:
            text: Long text to segment
            max_chars: Maximum characters per segment

        Returns:
            List of text segments
        """
        if len(text) <= max_chars:
            return [text]

        segments = []
        current_segment: List[str] = []
        current_length = 0

        # Split by sentences
        sentences = re.split(r"([.!?]+)", text)

        for i in range(0, len(sentences), 2):
            if i + 1 < len(sentences):
                sentence = sentences[i] + sentences[i + 1]
            else:
                sentence = sentences[i]

            sentence = sentence.strip()
            if not sentence:
                continue

            sentence_length = len(sentence)

            # If single sentence is too long, split by commas
            if sentence_length > max_chars:
                segments.extend(TextSegmenter._split_long_sentence(sentence, max_chars))
                continue

            # Check if adding this sentence exceeds limit
            if current_length + sentence_length > max_chars and current_segment:
                segments.append(" ".join(current_segment))
                current_segment = []
                current_length = 0

            current_segment.append(sentence)
            current_length += sentence_length + 1  # +1 for space

        # Add remaining
        if current_segment:
            segments.append(" ".join(current_segment))

        return segments

    @staticmethod
    def _split_long_sentence(sentence: str, max_chars: int) -> List[str]:
        """Split a long sentence into smaller parts"""
        if len(sentence) <= max_chars:
            return [sentence]

        # Try splitting by commas first
        parts = sentence.split(",")
        if len(parts) > 1:
            segments = []
            current: List[str] = []
            current_length = 0

            for part in parts:
                part = part.strip()
                if current_length + len(part) > max_chars and current:
                    segments.append(", ".join(current) + ",")
                    current = []
                    current_length = 0
                current.append(part)
                current_length += len(part) + 2  # +2 for ", "

            if current:
                segments.append(", ".join(current))
            return segments

        # If no commas, split by words
        words = sentence.split()
        segments = []
        current = []
        current_length = 0

        for word in words:
            if current_length + len(word) > max_chars and current:
                segments.append(" ".join(current))
                current = []
                current_length = 0
            current.append(word)
            current_length += len(word) + 1

        if current:
            segments.append(" ".join(current))

        return segments


def format_for_github_review(text: str) -> str:
    """
    Format text specifically for GitHub PR reviews

    Optimizes for professional yet friendly tone.
    """
    formatter = AudioTagFormatter()

    # Add professional greeting if not present
    if not text.lower().startswith(("hello", "hi", "hey", "thanks")):
        text = "[professional] " + text

    # Format with tags
    text = formatter.format_with_tags(text, auto_segment=True)

    # Add strategic pauses for readability
    text = text.replace("\n\n", "\n\n[pause: 0.5s]\n\n")

    return text


def format_for_documentation(text: str) -> str:
    """
    Format text for documentation reading

    Optimizes for clarity and comprehension.
    """
    formatter = AudioTagFormatter()

    # Ensure clear speech
    text = "[clear] " + text

    # Format with moderate segmentation
    text = formatter.format_with_tags(text, auto_segment=True)

    # Add pauses after headers (assumed to be lines ending with ':')
    text = re.sub(r"(.*:)\n", r"\1\n[pause: 0.3s]\n", text)

    return text


def format_for_error_message(text: str) -> str:
    """
    Format text for error messages

    Optimizes for clarity and appropriate concern.
    """
    formatter = AudioTagFormatter()

    # Add concerned tone
    if not any(tag in text for tag in ["[concerned]", "[serious]", "[professional]"]):
        text = "[concerned] " + text

    # Format without heavy segmentation
    text = formatter.format_with_tags(text, auto_segment=False)

    return text
