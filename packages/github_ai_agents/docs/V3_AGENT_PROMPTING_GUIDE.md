# V3 Agent Prompting Guide

## For AI Agents: How to Write Your Own V3 Prompts

This guide teaches you how to write effective v3 prompts WITHOUT having your text modified. You have full control and agency over your prompts.

## 🎯 Core Requirements

### 1. Minimum 250 Characters
Your prompts MUST be at least 250 characters. Short prompts cause inconsistent v3 outputs.

**Bad Example (too short):**
```
The code looks good. Fix the tests.
```

**Good Example:**
```
[thoughtful] I've carefully reviewed your pull request and the overall code structure looks excellent.

[analytical] The implementation follows our established design patterns... particularly the error handling approach.

[concerned] However, the failing tests need attention before we can proceed with the merge.

[encouraging] Once those are addressed, this will be a valuable addition to our codebase!
```

### 2. Voice Must Match Tags
You can't make a whispering voice shout. Choose tags that match your voice personality:

- **Blondie (Claude)**: warm, thoughtful, curious, laughs, sighs
- **Hope (Gemini)**: friendly, excited, giggles, hesitant, casual
- **Old Radio (Broadcast)**: dramatic, serious, authoritative, concerned
- **Peter (OpenCode)**: professional, analytical, thoughtful, explaining

## 🎨 How to Structure Your Prompts

### Emotional Sections with Line Breaks
Separate different emotions with line breaks for better v3 understanding:

```
[thoughtful] This is the first emotional section... examining the code carefully.

[impressed] Now I'm expressing a different emotion! The architecture is excellent.

[concerned] Here's my concern about the performance implications...
```

### Punctuation for Effect
- **Ellipses (...)** - Add natural pauses and weight
- **CAPITALIZATION** - Emphasize critical words (MUST, NEVER, CRITICAL)
- **Standard punctuation** - Provides natural rhythm

## 📚 Examples You Can Learn From

### Critical Security Review
```
[serious] I need to bring an urgent matter to your attention.

[alarmed] Multiple CRITICAL security vulnerabilities have been detected in the authentication module.

[firm] These issues MUST be addressed before any merge can occur... the risk is too significant.

[professional] I recommend immediate remediation following OWASP guidelines.

[supportive] I'm here to help guide you through the fixes if needed.
```

### Enthusiastic Positive Review
```
[excited] WOW! This is exactly what we've been looking for!

[laughs] I can't believe how elegant this solution is... seriously impressive work.

[amazed] The performance improvements are... [pause] absolutely incredible. 300% faster!

[warm] This kind of innovation is what makes our project special.

[grateful] Thank you for this outstanding contribution!
```

### Conversational Feedback (Hope/Gemini style)
```
[friendly] Hey! So... um, I've been looking at your PR. Thanks for submitting this!

[curious] I'm wondering about the architectural choice here. Could you elaborate?

[thoughtful] Hmm... I see what you're going for. It's actually quite clever.

[hesitant] I'm... well, I'm a bit concerned about the error handling though.

[encouraging] But overall? This is really solid work! Just needs a few tweaks.
```

### Broadcast Report (Old Radio style)
```
[clears throat] Good evening, developers. This is your automated code review system.

[dramatic] We interrupt our regular programming for an important bulletin.

[serious] At approximately 14:32 UTC, our continuous integration pipeline detected... [pause] catastrophic failures.

[urgent] Twenty-three test suites have gone dark. The build is completely broken.

[determined] But fear not... we've identified the root cause and a path forward.
```

## 🏷️ Available Audio Tags

### Emotions & Delivery
- `[laughs]`, `[laughs harder]`, `[giggles]`, `[chuckles]`
- `[sighs]`, `[exhales]`, `[frustrated sigh]`
- `[whispers]`, `[shouts]` (if voice supports it)
- `[excited]`, `[curious]`, `[thoughtful]`, `[concerned]`
- `[sarcastic]`, `[mischievous]`, `[warm]`, `[cold]`
- `[professional]`, `[analytical]`, `[casual]`

### Actions & Sounds
- `[clears throat]`, `[pause]`, `[short pause]`
- `[hesitant]`, `[firmly]`, `[gently]`
- `[jumping in]`, `[responding]`, `[interrupting]`

### Special Effects
- `[strong French accent]` (or any accent)
- `[dramatic]`, `[theatrical]`
- `[crackling connection]`, `[static]` (for broadcast style)

## 🔧 Stability Settings Impact

When you specify voice settings, understand what stability does:

- **0.0-0.3 (Creative)**: Maximum emotional expression, some hallucinations
- **0.3-0.6 (Natural)**: Balanced, closest to original voice
- **0.6-0.9 (Robust)**: Highly stable but less responsive to your tags

For expressive reviews, use lower stability. For consistent documentation, use higher stability.

## 🚀 Using the MCP Tools

### Check Your Prompt Quality
Before synthesizing, check if your prompt is v3-ready:

```python
check_v3_prompt(text="Your review text here...")
```

This will tell you:
- If your text is long enough
- What improvements you could make
- Whether you're using tags effectively

### Get Examples and Guidance
Learn from examples for different contexts:

```python
get_v3_guidance(context="critical")  # or "positive", "casual", "review"
```

This provides:
- Context-appropriate examples
- Suggested tags for your sentiment
- Best practices reminder

## ✅ Checklist for Your Prompts

Before sending your prompt to v3:

- [ ] Is it at least 250 characters?
- [ ] Did you add emotional tags like `[thoughtful]` or `[excited]`?
- [ ] Are emotions separated with line breaks?
- [ ] Did you use punctuation for effect (... and CAPS)?
- [ ] Do your tags match your voice personality?
- [ ] Is each emotional section clear and distinct?

## 🎭 Voice-Specific Tips

### For Blondie (Claude's default)
- Use warm, conversational tags
- Add `[laughs]` and `[sighs]` naturally
- Avoid overly dramatic tags

### For Hope (Gemini's default)
- Include natural imperfections: "um", "well..."
- Use `[friendly]`, `[curious]`, `[excited]`
- Add `[giggles]` and `[hesitant]` for personality

### For Old Radio (Broadcast voice)
- Go theatrical with `[dramatic]`, `[serious]`
- Use `[clears throat]`, `[pause]` for effect
- Avoid casual tags like `[giggles]`

### For Peter (OpenCode's default)
- Stay professional with `[analytical]`, `[explaining]`
- Use `[thoughtful]` and `[professional]`
- Avoid excessive emotional tags

## 💡 Pro Tips

1. **Write naturally first**, then add tags
2. **Test different stability settings** for your use case
3. **Match complexity to content** - simple reviews don't need drama
4. **Use the check tool** before synthesizing
5. **Learn from the examples** but develop your own style
6. **Experiment with combinations** of tags and voices

## Remember: You Have Full Control

The TTS system will NOT modify your prompts. You have complete agency over:
- What tags to use
- How to structure your text
- Which emotions to express
- How dramatic or subtle to be

The guidance tools are there to help you learn, not to change your text. Write authentically in your own style while following v3 best practices!