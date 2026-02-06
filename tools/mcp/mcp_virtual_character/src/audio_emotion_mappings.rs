//! Audio tag to emotion mappings for ElevenLabs integration.
//!
//! This module provides comprehensive mappings between ElevenLabs audio expression
//! tags and Virtual Character emotions, enabling automatic emotion detection from
//! synthesized speech.

use lazy_static::lazy_static;
use regex::Regex;
use std::collections::HashMap;

use crate::types::EmotionType;

/// Audio tag to emotion mapping with intensity.
pub type AudioTagMapping = (EmotionType, f32);

lazy_static! {
    /// ElevenLabs Audio Tag -> (EmotionType, intensity) mappings.
    /// Intensity range: 0.0 (subtle) to 1.0 (full expression)
    pub static ref AUDIO_TAG_TO_EMOTION: HashMap<&'static str, AudioTagMapping> = {
        let mut m = HashMap::new();

        // Joy/Happiness -> HAPPY or EXCITED
        m.insert("[laughs]", (EmotionType::Happy, 0.8));
        m.insert("[laughing]", (EmotionType::Happy, 0.8));
        m.insert("[chuckles]", (EmotionType::Happy, 0.5));
        m.insert("[giggles]", (EmotionType::Happy, 0.6));
        m.insert("[excited]", (EmotionType::Excited, 0.9));
        m.insert("[cheerfully]", (EmotionType::Happy, 0.7));
        m.insert("[happily]", (EmotionType::Happy, 0.6));
        m.insert("[joyfully]", (EmotionType::Happy, 0.8));
        m.insert("[delighted]", (EmotionType::Happy, 0.7));

        // Sadness -> SAD
        m.insert("[sighs]", (EmotionType::Sad, 0.4));
        m.insert("[sadly]", (EmotionType::Sad, 0.6));
        m.insert("[crying]", (EmotionType::Sad, 0.9));
        m.insert("[sobbing]", (EmotionType::Sad, 1.0));
        m.insert("[sniffles]", (EmotionType::Sad, 0.5));
        m.insert("[tearfully]", (EmotionType::Sad, 0.7));
        m.insert("[melancholy]", (EmotionType::Sad, 0.5));
        m.insert("[mournfully]", (EmotionType::Sad, 0.8));

        // Anger -> ANGRY
        m.insert("[angrily]", (EmotionType::Angry, 0.7));
        m.insert("[angry]", (EmotionType::Angry, 0.7));
        m.insert("[frustrated]", (EmotionType::Angry, 0.5));
        m.insert("[growls]", (EmotionType::Angry, 0.8));
        m.insert("[shouting]", (EmotionType::Angry, 0.9));
        m.insert("[yelling]", (EmotionType::Angry, 0.9));
        m.insert("[furiously]", (EmotionType::Angry, 1.0));
        m.insert("[irritated]", (EmotionType::Angry, 0.4));

        // Fear/Nervousness -> FEARFUL
        m.insert("[nervously]", (EmotionType::Fearful, 0.5));
        m.insert("[anxiously]", (EmotionType::Fearful, 0.6));
        m.insert("[scared]", (EmotionType::Fearful, 0.7));
        m.insert("[trembling]", (EmotionType::Fearful, 0.8));
        m.insert("[gasps]", (EmotionType::Fearful, 0.7));
        m.insert("[fearfully]", (EmotionType::Fearful, 0.7));
        m.insert("[terrified]", (EmotionType::Fearful, 1.0));
        m.insert("[worried]", (EmotionType::Fearful, 0.4));

        // Surprise -> SURPRISED
        m.insert("[surprised]", (EmotionType::Surprised, 0.7));
        m.insert("[amazed]", (EmotionType::Surprised, 0.8));
        m.insert("[shocked]", (EmotionType::Surprised, 0.9));
        m.insert("[stunned]", (EmotionType::Surprised, 0.9));
        m.insert("[astonished]", (EmotionType::Surprised, 0.9));
        m.insert("[wow]", (EmotionType::Surprised, 0.6));

        // Calm/Gentle -> CALM
        m.insert("[softly]", (EmotionType::Calm, 0.5));
        m.insert("[gently]", (EmotionType::Calm, 0.5));
        m.insert("[calmly]", (EmotionType::Calm, 0.6));
        m.insert("[peacefully]", (EmotionType::Calm, 0.7));
        m.insert("[whisper]", (EmotionType::Calm, 0.4));
        m.insert("[whispering]", (EmotionType::Calm, 0.4));
        m.insert("[soothingly]", (EmotionType::Calm, 0.6));
        m.insert("[quietly]", (EmotionType::Calm, 0.3));
        m.insert("[serenely]", (EmotionType::Calm, 0.7));

        // Disgust -> DISGUSTED
        m.insert("[disgusted]", (EmotionType::Disgusted, 0.7));
        m.insert("[grossed out]", (EmotionType::Disgusted, 0.6));
        m.insert("[revolted]", (EmotionType::Disgusted, 0.8));
        m.insert("[nauseated]", (EmotionType::Disgusted, 0.6));

        // Contempt -> CONTEMPTUOUS
        m.insert("[sarcastically]", (EmotionType::Contemptuous, 0.6));
        m.insert("[mockingly]", (EmotionType::Contemptuous, 0.7));
        m.insert("[dismissively]", (EmotionType::Contemptuous, 0.5));
        m.insert("[condescendingly]", (EmotionType::Contemptuous, 0.6));
        m.insert("[smugly]", (EmotionType::Contemptuous, 0.5));

        // Thinking/Consideration -> NEUTRAL (thoughtful neutral)
        m.insert("[thoughtfully]", (EmotionType::Neutral, 0.4));
        m.insert("[pondering]", (EmotionType::Neutral, 0.3));
        m.insert("[considering]", (EmotionType::Neutral, 0.3));
        m.insert("[hmm]", (EmotionType::Neutral, 0.2));
        m.insert("[musing]", (EmotionType::Neutral, 0.3));

        // Embarrassment -> mix (closest: SURPRISED with lower intensity)
        m.insert("[embarrassed]", (EmotionType::Surprised, 0.4));
        m.insert("[sheepishly]", (EmotionType::Surprised, 0.3));
        m.insert("[awkwardly]", (EmotionType::Surprised, 0.3));
        m.insert("[blushing]", (EmotionType::Surprised, 0.4));

        // Confident/Proud -> HAPPY (confident happiness)
        m.insert("[confidently]", (EmotionType::Happy, 0.5));
        m.insert("[proudly]", (EmotionType::Happy, 0.6));
        m.insert("[triumphantly]", (EmotionType::Excited, 0.8));

        // Bored/Tired -> NEUTRAL (disengaged)
        m.insert("[bored]", (EmotionType::Neutral, 0.2));
        m.insert("[yawns]", (EmotionType::Neutral, 0.3));
        m.insert("[tiredly]", (EmotionType::Neutral, 0.3));
        m.insert("[sleepily]", (EmotionType::Calm, 0.3));

        // Curious/Attentive -> NEUTRAL (alert)
        m.insert("[curiously]", (EmotionType::Neutral, 0.4));
        m.insert("[attentively]", (EmotionType::Neutral, 0.4));
        m.insert("[intrigued]", (EmotionType::Surprised, 0.4));

        m
    };

    /// Reverse mapping: Emotion -> List of (audio_tag, intensity)
    pub static ref EMOTION_TO_AUDIO_TAGS: HashMap<EmotionType, Vec<(&'static str, f32)>> = {
        let mut m: HashMap<EmotionType, Vec<(&'static str, f32)>> = HashMap::new();

        for (tag, (emotion, intensity)) in AUDIO_TAG_TO_EMOTION.iter() {
            m.entry(*emotion)
                .or_default()
                .push((*tag, *intensity));
        }

        // Sort by intensity descending for each emotion
        for tags in m.values_mut() {
            tags.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        }

        m
    };

    /// Regex for finding bracketed tags in text.
    static ref TAG_REGEX: Regex = Regex::new(r"\[[^\]]+\]").unwrap();
}

/// Extract emotions from text containing ElevenLabs audio tags.
///
/// # Arguments
/// * `text` - Text potentially containing audio tags like [laughs], [sighs]
///
/// # Returns
/// List of (EmotionType, intensity) tuples found in text
pub fn extract_emotions_from_text(text: &str) -> Vec<AudioTagMapping> {
    let mut emotions = Vec::new();
    let text_lower = text.to_lowercase();

    for cap in TAG_REGEX.find_iter(&text_lower) {
        let tag = cap.as_str();

        // Direct match
        if let Some(&mapping) = AUDIO_TAG_TO_EMOTION.get(tag) {
            emotions.push(mapping);
            continue;
        }

        // Fuzzy match - check if any known tag is contained
        let tag_content = &tag[1..tag.len() - 1]; // Remove brackets
        for (known_tag, mapping) in AUDIO_TAG_TO_EMOTION.iter() {
            let known_content = &known_tag[1..known_tag.len() - 1];
            if known_content.contains(tag_content) || tag_content.contains(known_content) {
                emotions.push(*mapping);
                break;
            }
        }
    }

    emotions
}

/// Get emotion for a single audio tag.
///
/// # Arguments
/// * `tag` - Audio tag like "[laughs]" or "laughs"
///
/// # Returns
/// (EmotionType, intensity) or None if not found
pub fn get_emotion_from_tag(tag: &str) -> Option<AudioTagMapping> {
    // Normalize: ensure brackets
    let normalized = if !tag.starts_with('[') {
        format!("[{}]", tag.trim_matches(']'))
    } else {
        tag.to_string()
    };

    let normalized = normalized.to_lowercase();
    AUDIO_TAG_TO_EMOTION.get(normalized.as_str()).copied()
}

/// Get suitable ElevenLabs audio tags for an emotion.
///
/// # Arguments
/// * `emotion` - The target EmotionType
/// * `intensity` - Desired intensity (0-1), tags closest to this are preferred
/// * `max_tags` - Maximum number of tags to return
///
/// # Returns
/// List of audio tags sorted by relevance to intensity
pub fn get_audio_tags_for_emotion(
    emotion: EmotionType,
    intensity: f32,
    max_tags: usize,
) -> Vec<&'static str> {
    let Some(candidates) = EMOTION_TO_AUDIO_TAGS.get(&emotion) else {
        return Vec::new();
    };

    // Sort by distance to desired intensity
    let mut sorted: Vec<_> = candidates.iter().collect();
    sorted.sort_by(|a, b| {
        let dist_a = (a.1 - intensity).abs();
        let dist_b = (b.1 - intensity).abs();
        dist_a
            .partial_cmp(&dist_b)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    sorted
        .into_iter()
        .take(max_tags)
        .map(|(tag, _)| *tag)
        .collect()
}

/// Get the dominant emotion from text with audio tags.
///
/// # Arguments
/// * `text` - Text containing audio tags
///
/// # Returns
/// The emotion with highest intensity, or None if no tags found
pub fn get_dominant_emotion(text: &str) -> Option<AudioTagMapping> {
    let emotions = extract_emotions_from_text(text);

    if emotions.is_empty() {
        return None;
    }

    // Return emotion with highest intensity
    emotions
        .into_iter()
        .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_extract_emotions_from_text() {
        let text = "She [laughs] and then [sighs] deeply.";
        let emotions = extract_emotions_from_text(text);
        assert_eq!(emotions.len(), 2);
        assert_eq!(emotions[0].0, EmotionType::Happy);
        assert_eq!(emotions[1].0, EmotionType::Sad);
    }

    #[test]
    fn test_get_emotion_from_tag() {
        let result = get_emotion_from_tag("[laughs]");
        assert!(result.is_some());
        let (emotion, intensity) = result.unwrap();
        assert_eq!(emotion, EmotionType::Happy);
        assert!((intensity - 0.8).abs() < 0.001);

        // Test without brackets
        let result = get_emotion_from_tag("crying");
        assert!(result.is_some());
        assert_eq!(result.unwrap().0, EmotionType::Sad);

        // Test unknown tag
        assert!(get_emotion_from_tag("[unknown]").is_none());
    }

    #[test]
    fn test_get_audio_tags_for_emotion() {
        let tags = get_audio_tags_for_emotion(EmotionType::Happy, 0.7, 2);
        assert!(!tags.is_empty());
        assert!(tags.len() <= 2);
    }

    #[test]
    fn test_get_dominant_emotion() {
        let text = "[laughs] [sobbing]"; // Happy 0.8, Sad 1.0
        let result = get_dominant_emotion(text);
        assert!(result.is_some());
        assert_eq!(result.unwrap().0, EmotionType::Sad); // Higher intensity

        let no_tags = "Just regular text.";
        assert!(get_dominant_emotion(no_tags).is_none());
    }

    #[test]
    fn test_emotion_to_audio_tags_reverse_mapping() {
        // Happy should have multiple tags
        let happy_tags = EMOTION_TO_AUDIO_TAGS.get(&EmotionType::Happy);
        assert!(happy_tags.is_some());
        assert!(happy_tags.unwrap().len() > 5);
    }

    #[test]
    fn test_all_major_emotions_have_mappings() {
        // Ensure all major emotions have at least one audio tag
        let emotions_to_check = [
            EmotionType::Happy,
            EmotionType::Sad,
            EmotionType::Angry,
            EmotionType::Fearful,
            EmotionType::Surprised,
            EmotionType::Calm,
            EmotionType::Disgusted,
            EmotionType::Contemptuous,
            EmotionType::Excited,
        ];

        for emotion in emotions_to_check {
            let tags = EMOTION_TO_AUDIO_TAGS.get(&emotion);
            assert!(tags.is_some(), "Missing tags for {:?}", emotion);
            assert!(!tags.unwrap().is_empty(), "Empty tags for {:?}", emotion);
        }
    }

    #[test]
    fn test_extract_multiple_same_emotions() {
        let text = "[laughs] [chuckles] [giggles]"; // All Happy with different intensities
        let emotions = extract_emotions_from_text(text);
        assert_eq!(emotions.len(), 3);
        for (emotion, _) in &emotions {
            assert_eq!(*emotion, EmotionType::Happy);
        }
    }

    #[test]
    fn test_case_insensitivity() {
        let upper = get_emotion_from_tag("[LAUGHS]");
        let lower = get_emotion_from_tag("[laughs]");
        assert!(upper.is_some());
        assert!(lower.is_some());
        assert_eq!(upper.unwrap().0, lower.unwrap().0);
    }

    #[test]
    fn test_brackets_with_extra_content() {
        // Test that partial matches work through fuzzy matching
        let text = "He said [laugh softly] nervously";
        let emotions = extract_emotions_from_text(text);
        // Fuzzy matching should find 'laugh' matches 'laughs'
        assert!(!emotions.is_empty());
    }

    #[test]
    fn test_intensity_sorting_in_reverse_mapping() {
        let sad_tags = EMOTION_TO_AUDIO_TAGS.get(&EmotionType::Sad);
        assert!(sad_tags.is_some());
        let tags = sad_tags.unwrap();

        // Verify sorted by intensity descending
        let mut prev_intensity = f32::MAX;
        for (_, intensity) in tags {
            assert!(
                *intensity <= prev_intensity,
                "Tags not sorted by descending intensity"
            );
            prev_intensity = *intensity;
        }
    }

    #[test]
    fn test_get_audio_tags_empty_for_missing_emotion() {
        // Neutral might have fewer or no high-intensity tags
        let tags = get_audio_tags_for_emotion(EmotionType::Neutral, 0.9, 5);
        // Should return whatever's available, not panic
        assert!(tags.len() <= 5);
    }

    #[test]
    fn test_fuzzy_matching() {
        // Test partial tag matching
        let text = "[laugh]"; // Missing 's'
        let emotions = extract_emotions_from_text(text);
        // Fuzzy matching should find 'laughs' contains 'laugh'
        assert!(!emotions.is_empty());
        assert_eq!(emotions[0].0, EmotionType::Happy);
    }
}
