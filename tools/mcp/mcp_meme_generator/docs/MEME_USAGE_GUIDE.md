# Meme Usage Guide

## Why Proper Meme Usage Matters

Memes aren't just images with text - they're cultural artifacts with specific contexts, tones, and usage patterns. Using a meme incorrectly is like using idioms wrong in a foreign language: at best it's awkward, at worst it completely changes the meaning.

## Critical Elements of Meme Usage

### 1. **Cultural Context**
Every meme comes from a specific source (TV show, movie, viral moment) that gives it meaning. Understanding this context is essential.

### 2. **Text Positioning**
Where text appears isn't arbitrary - it's part of the meme format. For example:
- "Ol' Reliable" text goes IN the spatula's label box, not as a caption
- Drake meme has rejection text on top, approval text on bottom
- Distracted boyfriend has specific positions for each character

### 3. **Phrasing Patterns**
Memes often follow specific linguistic patterns:
- "Ol' Reliable": "When [complex situation]" → "[simple solution]"
- "One Does Not Simply": "One does not simply [action]"
- "This is Fine": Used when everything is clearly NOT fine

### 4. **Tone and Intent**
Each meme carries a specific emotional tone:
- "Ol' Reliable": Affectionate nostalgia for simple solutions
- "This is Fine": Denial or dark humor about bad situations
- "Galaxy Brain": Escalating absurdity of solutions

## Template Documentation Structure

Each meme template configuration should include:

```json
{
  "name": "Template Name",
  "description": "Brief description",
  "cultural_context": "Origin and meaning of the meme",
  "text_positioning_note": "Critical positioning details",
  "usage_rules": [
    "When to use this meme",
    "Proper text structure",
    "Tone and intent",
    "Common mistakes to avoid"
  ],
  "examples": [
    {
      "top": "Example top text",
      "bottom": "Example bottom text",
      "explanation": "Why this works"
    }
  ]
}
```

## Common Mistakes to Avoid

### 1. **Wrong Text Placement**
❌ Putting "Ol' Reliable" text below the image
✅ Placing it in the white label on the spatula

### 2. **Mismatched Tone**
❌ Using "This is Fine" for actually fine situations
✅ Using it when things are clearly falling apart

### 3. **Incorrect Phrasing**
❌ "Ol' Reliable" with complex solution in the box
✅ Simple, basic solution that contrasts with the problem

### 4. **Missing Cultural Context**
❌ Using memes without understanding their origin
✅ Knowing why SpongeBob's spatula represents reliability

## Guidelines for AI Agents

When generating memes programmatically:

1. **Parse the template's usage_rules** - Don't just position text, understand the format
2. **Check cultural_context** - Ensure the meme fits the situation
3. **Follow phrasing patterns** - Use the linguistic structure the meme expects
4. **Validate tone match** - Make sure the emotion fits the meme's intent
5. **Review examples** - Learn from what works

## Adding New Templates

When adding a new meme template:

1. **Research the Origin**: Find the source material and understand why it became a meme
2. **Document Text Rules**: Specify exactly how text should be structured
3. **Explain Positioning**: Note any critical positioning (like text in specific areas)
4. **Provide Good Examples**: Show 3-5 examples that demonstrate proper usage
5. **Note Common Errors**: Document what NOT to do

## Testing Meme Understanding

Before using a meme generator, test understanding:

```python
# Good: Shows understanding of contrast
{
  "template": "ol_reliable",
  "top": "When Kubernetes won't start",
  "bottom": "docker run"
}

# Bad: Missing the simplicity aspect
{
  "template": "ol_reliable",
  "top": "When the server crashes",
  "bottom": "distributed fault-tolerant architecture"
}
```

## Conclusion

Memes are a language. Like any language, they have grammar (positioning), vocabulary (phrasing), and cultural context (origin/meaning). Respecting these elements is the difference between effective communication and digital cringe.

Remember: **A meme used correctly amplifies your message. A meme used incorrectly becomes the message.**
