# ElevenLabs v3 Audio Tags Complete Reference

Comprehensive guide to all audio tags supported by ElevenLabs v3 model.

## Table of Contents

1. [Overview](#overview)
2. [Emotional Context](#emotional-context)
3. [Reactions & Non-Verbal](#reactions--non-verbal)
4. [Delivery Styles](#delivery-styles)
5. [Pacing & Tempo](#pacing--tempo)
6. [Accents & Voices](#accents--voices)
7. [Environmental Sounds](#environmental-sounds)
8. [Advanced Combinations](#advanced-combinations)
9. [Best Practices](#best-practices)

## Overview

Audio tags in ElevenLabs v3 provide precise control over speech synthesis. Tags are placed in square brackets `[tag]` and can be combined for layered effects.

### Important Notes

- **Model Requirement**: Only works with `eleven_v3` model
- **Voice Settings**: Lower stability (0.3-0.5) = more expressive
- **Case Sensitivity**: Some tags are case-sensitive (`[WHISPER]` vs `[whispers]`)
- **Placement**: Tags can be placed anywhere in text

## Emotional Context

### Basic Emotions

| Tag | Effect | Example |
|-----|--------|---------|
| `[happy]` | Cheerful tone | `[happy] What a beautiful day!` |
| `[sad]` | Melancholic delivery | `[sad] I miss those times.` |
| `[angry]` | Aggressive tone | `[angry] This is unacceptable!` |
| `[excited]` | Enthusiastic energy | `[excited] I can't wait to show you!` |
| `[nervous]` | Anxious delivery | `[nervous] I'm not sure about this...` |
| `[curious]` | Inquisitive tone | `[curious] How does that work?` |
| `[confused]` | Puzzled delivery | `[confused] Wait, what do you mean?` |
| `[tired]` | Exhausted tone | `[tired] I need some rest.` |

### Nuanced Emotions

| Tag | Effect | Example |
|-----|--------|---------|
| `[cheerfully]` | Bright, upbeat | `[cheerfully] Good morning everyone!` |
| `[playfully]` | Teasing, fun | `[playfully] Oh, you think so?` |
| `[regretful]` | Remorseful | `[regretful] I wish I had done differently.` |
| `[resigned tone]` | Accepting defeat | `[resigned tone] I suppose you're right.` |
| `[deadpan]` | Emotionless | `[deadpan] How hilarious.` |
| `[flatly]` | Monotone | `[flatly] That's just great.` |
| `[thoughtfully]` | Contemplative | `[thoughtfully] Let me consider that.` |
| `[sarcastic]` | Mocking tone | `[sarcastic] Oh, brilliant idea.` |
| `[sorrowful]` | Deep sadness | `[sorrowful] It's truly heartbreaking.` |

## Reactions & Non-Verbal

### Laughter

| Tag | Effect | Example |
|-----|--------|---------|
| `[laughs]` | Normal laugh | `That's funny! [laughs]` |
| `[laughs harder]` | Intense laughter | `[laughs harder] Stop, I can't breathe!` |
| `[starts laughing]` | Beginning to laugh | `Wait... [starts laughing] did you really?` |
| `[chuckles]` | Light laugh | `[chuckles] Nice try.` |
| `[giggles]` | Soft, light laugh | `[giggles] That tickles!` |
| `[wheezing]` | Laughing hard | `[wheezing] That's too much!` |

### Sighs & Breathing

| Tag | Effect | Example |
|-----|--------|---------|
| `[sighs]` | Normal sigh | `[sighs] Here we go again.` |
| `[SIGH]` | Heavy sigh | `[SIGH] This is exhausting.` |
| `[breathes]` | Audible breath | `[breathes] Okay, let's continue.` |
| `[gasps]` | Sharp intake | `[gasps] No way!` |
| `[gasp]` | Single gasp | `[gasp] That's incredible!` |

### Emotional Reactions

| Tag | Effect | Example |
|-----|--------|---------|
| `[crying]` | Crying sounds | `[crying] I can't believe it's over.` |
| `[sobbing]` | Heavy crying | `[sobbing] Why did this happen?` |
| `[sniffs]` | Sniffling | `[sniffs] I'm fine, really.` |
| `[gulps]` | Nervous swallow | `[gulps] That's a big spider.` |
| `[groans]` | Frustrated sound | `[groans] Not again!` |
| `[scoffs]` | Dismissive sound | `[scoffs] As if that would work.` |

### Speech Interruptions

| Tag | Effect | Example |
|-----|--------|---------|
| `[clears throat]` | Throat clearing | `[clears throat] As I was saying...` |
| `[hesitates]` | Uncertain pause | `I think... [hesitates] maybe we should wait.` |
| `[stammers]` | Stuttering | `[stammers] I-I don't know what to say.` |

## Delivery Styles

### Volume Control

| Tag | Effect | Example |
|-----|--------|---------|
| `[WHISPER]` | Very quiet | `[WHISPER] Don't let them hear us.` |
| `[whispers]` | Soft speech | `[whispers] It's a secret.` |
| `[SHOUTING]` | Very loud | `[SHOUTING] GET DOWN NOW!` |
| `[shouts]` | Loud speech | `[shouts] Hey, over here!` |
| `[yelling]` | Sustained loud | `[yelling] Stop right there!` |
| `[murmuring]` | Low, indistinct | `[murmuring] I can't believe this...` |
| `[mutters]` | Quiet grumbling | `[mutters] This is ridiculous.` |

### Speech Styles

| Tag | Effect | Example |
|-----|--------|---------|
| `[announcing]` | Clear, formal | `[announcing] Ladies and gentlemen!` |
| `[narrating]` | Storytelling tone | `[narrating] Once upon a time...` |
| `[exclaims]` | Emphatic | `[exclaims] That's amazing!` |

## Pacing & Tempo

### Speed Control

| Tag | Effect | Example |
|-----|--------|---------|
| `[rushed]` | Fast speech | `[rushed] We need to go now!` |
| `[slows down]` | Slower pace | `Let me explain... [slows down] carefully.` |
| `[deliberate]` | Measured pace | `[deliberate] Each. Word. Matters.` |
| `[rapid-fire]` | Very fast | `[rapid-fire] Facts facts facts!` |
| `[drawn out]` | Elongated | `[drawn out] Nooooo way!` |

### Pauses & Timing

| Tag | Effect | Example |
|-----|--------|---------|
| `[pause]` | Brief pause | `Think about it [pause] really think.` |
| `[continues after a beat]` | Timed pause | `Well [continues after a beat] I suppose.` |

### Delivery Confidence

| Tag | Effect | Example |
|-----|--------|---------|
| `[timidly]` | Shy, quiet | `[timidly] Excuse me?` |
| `[confidently]` | Strong, assured | `[confidently] I know I can do this.` |
| `[uncertainly]` | Doubtful | `[uncertainly] Maybe... I think?` |

## Accents & Voices

### Regional Accents

| Tag | Effect | Example |
|-----|--------|---------|
| `[American accent]` | US accent | `[American accent] Howdy partner!` |
| `[British accent]` | UK accent | `[British accent] Cheerio!` |
| `[Southern US accent]` | Southern drawl | `[Southern US accent] Well, bless your heart.` |
| `[Australian accent]` | Aussie accent | `[Australian accent] G'day mate!` |
| `[Irish accent]` | Irish brogue | `[Irish accent] Top of the morning!` |
| `[Scottish accent]` | Scottish accent | `[Scottish accent] Och, laddie!` |

### International Accents

| Tag | Effect | Example |
|-----|--------|---------|
| `[French accent]` | French accent | `[French accent] Bonjour, mon ami!` |
| `[German accent]` | German accent | `[German accent] Guten Tag!` |
| `[Italian accent]` | Italian accent | `[Italian accent] Mamma mia!` |
| `[Spanish accent]` | Spanish accent | `[Spanish accent] Hola, amigo!` |
| `[Russian accent]` | Russian accent | `[Russian accent] Da, comrade.` |

### Character Voices

| Tag | Effect | Example |
|-----|--------|---------|
| `[pirate voice]` | Pirate speech | `[pirate voice] Ahoy, matey!` |
| `[robot voice]` | Robotic tone | `[robot voice] Processing request.` |

## Environmental Sounds

### Action Sounds

| Tag | Effect | Example |
|-----|--------|---------|
| `[gunshot]` | Gun firing | `Duck! [gunshot]` |
| `[explosion]` | Explosion sound | `[explosion] The building collapsed!` |
| `[clapping]` | Applause | `Thank you! [clapping]` |

### Physical Sounds

| Tag | Effect | Example |
|-----|--------|---------|
| `[door slam]` | Door closing hard | `[door slam] And stay out!` |
| `[footsteps]` | Walking sounds | `[footsteps] Someone's coming.` |

### Weather Sounds

| Tag | Effect | Example |
|-----|--------|---------|
| `[thunder]` | Thunder rumble | `[thunder] The storm is here.` |
| `[wind]` | Wind blowing | `[wind] It's getting cold.` |
| `[rain]` | Rain sounds | `[rain] Let's stay inside.` |

## Advanced Combinations

### Layered Emotions

```
[nervously][whispers] "I don't think we should be here..."
[happily][shouts][laughs] "We did it! We actually did it!"
[sad][crying][slows down] "It's... it's finally over."
[angry][rapid-fire] "No no no, this is wrong!"
[thoughtfully][pause][continues after a beat] "Perhaps there's another way."
```

### Scene Setting

```
[thunder][rain][SHOUTING] "We need to find shelter!"
[door slam][angry] "I've had enough of this!"
[footsteps][whispers] "Someone's coming... hide!"
[explosion][gasps][yelling] "Everyone get down!"
```

### Character Development

```
Start: [timidly] "I'm not sure I can do this..."
Middle: [nervously][breathes] "Okay, here goes nothing."
End: [confidently][excited] "I did it! I really did it!"
```

### Dramatic Dialogue

```
Character A: [curious] "What's in the box?"
Character B: [mysteriously][whispers] "You don't want to know..."
Character A: [nervous][gulps] "Now I have to know."
Character B: [dramatically][pause] "Your... destiny."
Character A: [confused][laughs] "What?"
```

## Best Practices

### Do's ✅

1. **Test Different Combinations**: Some tags work better together
2. **Match Voice to Tags**: Some voices respond better to certain tags
3. **Use Appropriate Stability**: Lower (0.3) for emotions, higher (0.7) for consistency
4. **Place Tags Strategically**: Beginning for tone, middle for reactions
5. **Consider Context**: GitHub reviews vs storytelling need different approaches

### Don'ts ❌

1. **Don't Overuse Tags**: Too many can sound unnatural
2. **Don't Mix Conflicting Emotions**: `[happy][sad]` confuses the model
3. **Don't Expect All Tags on All Voices**: Some voices have limitations
4. **Don't Use with Wrong Models**: Only `eleven_v3` fully supports tags
5. **Don't Ignore Punctuation**: It affects tag interpretation

### Optimization Tips

#### For Maximum Expression
```python
voice_settings = {
    "stability": 0.3,  # Creative mode
    "similarity_boost": 0.8,
    "style": 0.6,
    "use_speaker_boost": true
}
```

#### For Consistent Delivery
```python
voice_settings = {
    "stability": 0.7,  # More stable
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": false
}
```

### Common Patterns

#### Professional Review
```
[thoughtfully] "Looking at the implementation..."
[impressed] "The error handling is excellent!"
[concerned] "However, the performance might be an issue."
[optimistic] "With these changes, it'll be perfect!"
```

#### Storytelling
```
[narrating] "It was a dark and stormy night."
[mysteriously] "Something moved in the shadows."
[whispers] "Then, a voice called out..."
[dramatically][shouts] "Who goes there?!"
```

#### Tutorial Narration
```
[cheerfully] "Welcome to this tutorial!"
[clearly] "First, open your terminal."
[encouraging] "Great! Now type this command."
[excited] "Perfect! You've completed the setup!"
```

## Troubleshooting

### Tags Not Working?

1. **Check Model**: Must be using `eleven_v3`
2. **Verify Syntax**: `[tag]` not `{tag}` or `(tag)`
3. **Test Stability**: Try lowering to 0.3-0.4
4. **Try Different Voice**: Some voices respond better
5. **Simplify**: Start with one tag, then add more

### Unexpected Results?

- **Too Robotic**: Lower stability, increase style
- **Too Wild**: Increase stability, decrease style
- **Missing Emotion**: Add punctuation for emphasis
- **Wrong Accent**: Ensure voice supports accents
- **No Effect**: Verify v3 model is selected

## Examples by Use Case

### GitHub PR Review
```
[professional] "Thank you for your contribution."
[impressed] "The architecture is well thought out!"
[thoughtfully] "One suggestion: consider caching here."
[enthusiastic] "Looking forward to the next iteration!"
```

### Customer Support
```
[friendly] "Hello! How can I help you today?"
[concerned] "I understand your frustration."
[helpful] "Let me walk you through the solution."
[cheerful] "Is there anything else I can help with?"
```

### Educational Content
```
[welcoming] "Welcome to today's lesson!"
[clearly] "Let's start with the basics."
[encouraging] "You're doing great!"
[congratulations] "Excellent work!"
```

---

Remember: The key to great audio synthesis is experimentation. Try different combinations to find what works best for your specific use case!
