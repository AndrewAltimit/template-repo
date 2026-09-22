//! Audio tag to emotion mappings for ElevenLabs integration.
//!
//! Maps ElevenLabs v3 audio expression tags (for example `[laughs]` or
//! `[whispering]`) to character emotions with an intensity, so that speech can
//! drive the avatar's expression automatically.
//!
//! Lookup is exact first, then a deterministic word/stem fuzzy match so that
//! variants such as `[laugh]` or `[laughs softly]` still resolve.

use regex::Regex;
use std::collections::HashMap;
use std::sync::LazyLock;

use crate::types::EmotionType;

/// Audio tag to emotion mapping with intensity.
pub type AudioTagMapping = (EmotionType, f32);

/// Raw table: tag content (without brackets) -> emotion, intensity (0..=1).
const TAG_TABLE: &[(&str, EmotionType, f32)] = &[
    ("laughs", EmotionType::Happy, 0.8),
    ("laughing", EmotionType::Happy, 0.8),
    ("chuckles", EmotionType::Happy, 0.5),
    ("giggles", EmotionType::Happy, 0.6),
    ("excited", EmotionType::Excited, 0.9),
    ("cheerfully", EmotionType::Happy, 0.7),
    ("happily", EmotionType::Happy, 0.6),
    ("joyfully", EmotionType::Happy, 0.8),
    ("delighted", EmotionType::Happy, 0.7),
    ("sighs", EmotionType::Sad, 0.4),
    ("sadly", EmotionType::Sad, 0.6),
    ("crying", EmotionType::Sad, 0.9),
    ("sobbing", EmotionType::Sad, 1.0),
    ("sniffles", EmotionType::Sad, 0.5),
    ("tearfully", EmotionType::Sad, 0.7),
    ("melancholy", EmotionType::Sad, 0.5),
    ("mournfully", EmotionType::Sad, 0.8),
    ("angrily", EmotionType::Angry, 0.7),
    ("angry", EmotionType::Angry, 0.7),
    ("frustrated", EmotionType::Angry, 0.5),
    ("growls", EmotionType::Angry, 0.8),
    ("shouting", EmotionType::Angry, 0.9),
    ("yelling", EmotionType::Angry, 0.9),
    ("furiously", EmotionType::Angry, 1.0),
    ("irritated", EmotionType::Angry, 0.4),
    ("nervously", EmotionType::Fearful, 0.5),
    ("anxiously", EmotionType::Fearful, 0.6),
    ("scared", EmotionType::Fearful, 0.7),
    ("trembling", EmotionType::Fearful, 0.8),
    ("gasps", EmotionType::Fearful, 0.7),
    ("fearfully", EmotionType::Fearful, 0.7),
    ("terrified", EmotionType::Fearful, 1.0),
    ("worried", EmotionType::Fearful, 0.4),
    ("surprised", EmotionType::Surprised, 0.7),
    ("amazed", EmotionType::Surprised, 0.8),
    ("shocked", EmotionType::Surprised, 0.9),
    ("stunned", EmotionType::Surprised, 0.9),
    ("astonished", EmotionType::Surprised, 0.9),
    ("wow", EmotionType::Surprised, 0.6),
    ("softly", EmotionType::Calm, 0.5),
    ("gently", EmotionType::Calm, 0.5),
    ("calmly", EmotionType::Calm, 0.6),
    ("peacefully", EmotionType::Calm, 0.7),
    ("whisper", EmotionType::Calm, 0.4),
    ("whispering", EmotionType::Calm, 0.4),
    ("soothingly", EmotionType::Calm, 0.6),
    ("quietly", EmotionType::Calm, 0.3),
    ("serenely", EmotionType::Calm, 0.7),
    ("disgusted", EmotionType::Disgusted, 0.7),
    ("grossed out", EmotionType::Disgusted, 0.6),
    ("revolted", EmotionType::Disgusted, 0.8),
    ("nauseated", EmotionType::Disgusted, 0.6),
    ("sarcastically", EmotionType::Contemptuous, 0.6),
    ("mockingly", EmotionType::Contemptuous, 0.7),
    ("dismissively", EmotionType::Contemptuous, 0.5),
    ("condescendingly", EmotionType::Contemptuous, 0.6),
    ("smugly", EmotionType::Contemptuous, 0.5),
    ("thoughtfully", EmotionType::Neutral, 0.4),
    ("pondering", EmotionType::Neutral, 0.3),
    ("considering", EmotionType::Neutral, 0.3),
    ("hmm", EmotionType::Neutral, 0.2),
    ("musing", EmotionType::Neutral, 0.3),
    ("embarrassed", EmotionType::Surprised, 0.4),
    ("sheepishly", EmotionType::Surprised, 0.3),
    ("awkwardly", EmotionType::Surprised, 0.3),
    ("blushing", EmotionType::Surprised, 0.4),
    ("confidently", EmotionType::Happy, 0.5),
    ("proudly", EmotionType::Happy, 0.6),
    ("triumphantly", EmotionType::Excited, 0.8),
    ("bored", EmotionType::Neutral, 0.2),
    ("yawns", EmotionType::Neutral, 0.3),
    ("tiredly", EmotionType::Neutral, 0.3),
    ("sleepily", EmotionType::Calm, 0.3),
    ("curiously", EmotionType::Neutral, 0.4),
    ("attentively", EmotionType::Neutral, 0.4),
    ("intrigued", EmotionType::Surprised, 0.4),
    // Additional common v3 tags
    ("smiles", EmotionType::Happy, 0.6),
    ("grins", EmotionType::Happy, 0.6),
    ("pleased", EmotionType::Happy, 0.7),
    ("cries", EmotionType::Sad, 0.9),
    ("sobs", EmotionType::Sad, 0.9),
    ("sighing", EmotionType::Sad, 0.4),
    ("whimpers", EmotionType::Sad, 0.7),
    ("snarls", EmotionType::Angry, 0.8),
    ("scoffs", EmotionType::Angry, 0.5),
    ("huffs", EmotionType::Angry, 0.5),
    ("shouts", EmotionType::Angry, 0.9),
    ("yells", EmotionType::Angry, 0.9),
    ("exclaims", EmotionType::Surprised, 0.7),
    ("trembles", EmotionType::Fearful, 0.7),
    ("screams", EmotionType::Fearful, 0.9),
    ("screaming", EmotionType::Fearful, 0.9),
    ("whispers", EmotionType::Calm, 0.4),
    ("murmurs", EmotionType::Calm, 0.4),
    ("mutters", EmotionType::Calm, 0.4),
    ("hums", EmotionType::Calm, 0.5),
    ("humming", EmotionType::Calm, 0.5),
    ("cheers", EmotionType::Excited, 0.9),
    ("cheering", EmotionType::Excited, 0.9),
    ("excitedly", EmotionType::Excited, 0.8),
];

/// ElevenLabs audio tag (with brackets, lowercase) -> (EmotionType, intensity).
pub static AUDIO_TAG_TO_EMOTION: LazyLock<HashMap<String, AudioTagMapping>> = LazyLock::new(|| {
    TAG_TABLE
        .iter()
        .map(|(tag, emotion, intensity)| (format!("[{tag}]"), (*emotion, *intensity)))
        .collect()
});

/// Reverse mapping: Emotion -> list of (audio_tag, intensity), sorted by
/// intensity descending (ties broken by tag name for determinism).
pub static EMOTION_TO_AUDIO_TAGS: LazyLock<HashMap<EmotionType, Vec<(String, f32)>>> =
    LazyLock::new(|| {
        let mut m: HashMap<EmotionType, Vec<(String, f32)>> = HashMap::new();
        for (tag, emotion, intensity) in TAG_TABLE {
            m.entry(*emotion)
                .or_default()
                .push((format!("[{tag}]"), *intensity));
        }
        for tags in m.values_mut() {
            tags.sort_by(|a, b| {
                b.1.partial_cmp(&a.1)
                    .unwrap_or(std::cmp::Ordering::Equal)
                    .then_with(|| a.0.cmp(&b.0))
            });
        }
        m
    });

/// Regex for finding bracketed tags in text.
static TAG_REGEX: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\[[^\[\]]+\]").expect("static tag regex is valid"));

/// Minimum word length considered by fuzzy matching (avoids `[a]` matching
/// everything).
const MIN_FUZZY_LEN: usize = 3;

/// Look up tag *content* (lowercase, no brackets): exact first, then per-word
/// exact, then per-word stem match (`laugh` ~ `laughs`). Deterministic.
fn lookup_content(content: &str) -> Option<AudioTagMapping> {
    let content = content.trim();
    if content.is_empty() {
        return None;
    }
    if let Some((_, e, i)) = TAG_TABLE.iter().find(|(t, _, _)| *t == content) {
        return Some((*e, *i));
    }

    for word in content.split_whitespace() {
        let word = word.trim_matches(|c: char| !c.is_alphanumeric());
        if word.len() < MIN_FUZZY_LEN {
            continue;
        }
        if let Some((_, e, i)) = TAG_TABLE.iter().find(|(t, _, _)| *t == word) {
            return Some((*e, *i));
        }
        // Stem match: prefer the candidate whose length is closest to the
        // word, then alphabetical order, so results never depend on hashing.
        let best = TAG_TABLE
            .iter()
            .filter(|(t, _, _)| {
                t.len() >= MIN_FUZZY_LEN
                    && !t.contains(' ')
                    && (t.starts_with(word) || word.starts_with(t))
            })
            .min_by(|a, b| {
                let da = a.0.len().abs_diff(word.len());
                let db = b.0.len().abs_diff(word.len());
                da.cmp(&db).then_with(|| a.0.cmp(b.0))
            });
        if let Some((_, e, i)) = best {
            return Some((*e, *i));
        }
    }
    None
}

/// Extract emotions from text containing ElevenLabs audio tags, in order of
/// appearance. Unknown tags are skipped.
pub fn extract_emotions_from_text(text: &str) -> Vec<AudioTagMapping> {
    let text_lower = text.to_lowercase();
    TAG_REGEX
        .find_iter(&text_lower)
        .filter_map(|m| {
            let tag = m.as_str();
            lookup_content(&tag[1..tag.len() - 1])
        })
        .collect()
}

/// Extract the raw bracketed tags (for example `"[laughs]"`) from text.
pub fn extract_tags_from_text(text: &str) -> Vec<String> {
    TAG_REGEX
        .find_iter(text)
        .map(|m| m.as_str().to_string())
        .collect()
}

/// Remove bracketed audio tags from text and collapse whitespace (for display,
/// e.g. the VRChat chatbox).
pub fn strip_tags(text: &str) -> String {
    let stripped = TAG_REGEX.replace_all(text, " ");
    stripped.split_whitespace().collect::<Vec<_>>().join(" ")
}

/// Get emotion for a single audio tag (`"[laughs]"` or `"laughs"`).
pub fn get_emotion_from_tag(tag: &str) -> Option<AudioTagMapping> {
    let lower = tag.trim().to_lowercase();
    let content = lower.trim_start_matches('[').trim_end_matches(']');
    lookup_content(content)
}

/// Get suitable ElevenLabs audio tags for an emotion, ordered by closeness of
/// their intensity to `intensity`.
pub fn get_audio_tags_for_emotion(
    emotion: EmotionType,
    intensity: f32,
    max_tags: usize,
) -> Vec<String> {
    let Some(candidates) = EMOTION_TO_AUDIO_TAGS.get(&emotion) else {
        return Vec::new();
    };

    let mut sorted: Vec<_> = candidates.iter().collect();
    sorted.sort_by(|a, b| {
        let dist_a = (a.1 - intensity).abs();
        let dist_b = (b.1 - intensity).abs();
        dist_a
            .partial_cmp(&dist_b)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.0.cmp(&b.0))
    });

    sorted
        .into_iter()
        .take(max_tags)
        .map(|(tag, _)| tag.clone())
        .collect()
}

/// Get the dominant (highest-intensity) emotion from text with audio tags.
/// On ties the first occurrence wins.
pub fn get_dominant_emotion(text: &str) -> Option<AudioTagMapping> {
    dominant(extract_emotions_from_text(text))
}

/// Dominant emotion of a list of individual tags (`["[laughs]", "sighs"]`).
pub fn get_dominant_emotion_from_tags<S: AsRef<str>>(tags: &[S]) -> Option<AudioTagMapping> {
    dominant(
        tags.iter()
            .filter_map(|t| get_emotion_from_tag(t.as_ref()))
            .collect(),
    )
}

fn dominant(emotions: Vec<AudioTagMapping>) -> Option<AudioTagMapping> {
    emotions.into_iter().fold(None, |best, cur| match best {
        Some(b) if b.1 >= cur.1 => Some(b),
        _ => Some(cur),
    })
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

    #[test]
    fn test_fuzzy_matching_is_deterministic_and_word_based() {
        // "laugh softly" must resolve through the first word ("laugh" ->
        // "laughs"), not whichever table entry a hash map yields first.
        for _ in 0..20 {
            let e = extract_emotions_from_text("[laugh softly]");
            assert_eq!(e, vec![(EmotionType::Happy, 0.8)]);
        }
    }

    #[test]
    fn test_short_tags_do_not_fuzzy_match() {
        assert!(extract_emotions_from_text("[a] [x] [ok]").is_empty());
        assert!(get_emotion_from_tag("").is_none());
    }

    #[test]
    fn test_strip_and_extract_tags() {
        let text = "Hello! [laughs] I'm so [whispering] happy.";
        assert_eq!(strip_tags(text), "Hello! I'm so happy.");
        assert_eq!(
            extract_tags_from_text(text),
            vec!["[laughs]".to_string(), "[whispering]".to_string()]
        );
    }

    #[test]
    fn test_dominant_from_tags() {
        let d = get_dominant_emotion_from_tags(&["[sighs]", "sobbing", "[nope]"]).unwrap();
        assert_eq!(d.0, EmotionType::Sad);
        assert!((d.1 - 1.0).abs() < f32::EPSILON);
        assert!(get_dominant_emotion_from_tags::<&str>(&[]).is_none());
    }

    #[test]
    fn test_additional_tags_present() {
        assert_eq!(
            get_emotion_from_tag("[giggles]").unwrap().0,
            EmotionType::Happy
        );
        assert_eq!(
            get_emotion_from_tag("screams").unwrap().0,
            EmotionType::Fearful
        );
        assert_eq!(
            get_emotion_from_tag("[cheering]").unwrap().0,
            EmotionType::Excited
        );
    }
}
