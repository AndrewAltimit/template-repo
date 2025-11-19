#!/usr/bin/env python3
"""
Consolidate multiple Gemini review sections into a single cohesive review.

This script takes multiple review section files (one per file type) and uses
Gemini to consolidate them into a single, well-structured review with:
- Removed repetitive reactions
- Consolidated observations
- Natural flow
- Single reaction at the end
"""

import asyncio
import sys
from pathlib import Path
from typing import List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from packages.github_agents.src.github_agents.agents.gemini import (  # noqa: E402
    GeminiAgent,
)


async def consolidate_reviews(review_files: List[Path], pr_info: dict) -> Tuple[str, str]:
    """
    Consolidate multiple review sections into a single cohesive review.

    Args:
        review_files: List of paths to review section files
        pr_info: Dictionary with PR information

    Returns:
        Tuple of (consolidated_review, model_used)
    """
    # Read all review sections
    sections = []
    for file_path in review_files:
        if file_path.exists():
            section_name = file_path.stem.replace("review_", "").replace("_", " ").title()
            content = file_path.read_text(encoding="utf-8")
            sections.append(f"## {section_name}\n{content}")

    if not sections:
        return "No review sections found to consolidate.", "none"

    # Create consolidation prompt
    combined_sections = "\n".join(sections)
    pr_num = pr_info["number"]
    pr_title = pr_info["title"]
    consolidation_prompt = f"""You are reviewing PR #{pr_num}: {pr_title}

You have received multiple review sections for different file types.
Your task is to consolidate these into a single, cohesive code review that:

1. **Removes Repetitive Content**: Consolidate duplicate observations and reactions
2. **Natural Flow**: Organize feedback logically (critical issues first, then improvements, then positive notes)
3. **Single Reaction**: Use ONE reaction image at the end that best represents your overall assessment
4. **Professional Tone**: Maintain the analytical, precise tone while being concise
5. **Action Items**: Group actionable items clearly

**Review Sections to Consolidate:**

{combined_sections}

**Consolidation Guidelines:**
- If multiple sections mention the same issue (e.g., "GPU requirements"), merge them into one clear statement
- Remove reaction images from individual sections - you'll add ONE at the very end
- Keep specific file references and line numbers
- Preserve all technical details and security concerns
- Use markdown headings for organization:
  - ## 🔴 Critical Issues (if any)
  - ## ⚠️ Architecture & Best Practices (if any)
  - ## ✅ Positive Changes (what's done well)
  - ## 📋 Recommendations (action items)

**Final Reaction**: Choose ONE reaction that best represents the review:
- `rem_glasses.png` - Analytical approval, changes are technically sound
- `miku_confused.png` - Significant concerns that need addressing
- `youre_absolutely_right.png` - Full agreement with approach
- `thinking_foxgirl.png` - Needs careful consideration

Generate the consolidated review now:"""

    # Use Gemini agent to consolidate
    agent = GeminiAgent()
    try:
        result = await agent.execute({"prompt": consolidation_prompt})
        consolidated_review = result.get("output", "")
        model_used = result.get("model", "gemini-3-pro-preview")

        return consolidated_review, model_used
    except Exception as e:
        print(f"Error during consolidation: {e}")
        # Fallback: just concatenate sections
        fallback = "\n\n".join(sections)
        return fallback, "none"


async def main():
    """Main entry point for consolidation script."""
    if len(sys.argv) < 3:
        print("Usage: consolidate-gemini-review.py <review_dir> <pr_number> [pr_title]")
        sys.exit(1)

    review_dir = Path(sys.argv[1])
    pr_number = sys.argv[2]
    pr_title = sys.argv[3] if len(sys.argv) > 3 else f"PR #{pr_number}"

    if not review_dir.exists():
        print(f"Error: Review directory {review_dir} does not exist")
        sys.exit(1)

    # Find all review section files
    review_files = sorted(review_dir.glob("review_*.txt"))

    if not review_files:
        print(f"Error: No review section files found in {review_dir}")
        sys.exit(1)

    print(f"Found {len(review_files)} review sections to consolidate:")
    for f in review_files:
        print(f"  - {f.name}")

    pr_info = {"number": pr_number, "title": pr_title}

    print("\nConsolidating reviews with Gemini...")
    consolidated, model = await consolidate_reviews(review_files, pr_info)

    # Save consolidated review
    output_file = review_dir / "review_consolidated.txt"
    output_file.write_text(consolidated, encoding="utf-8")

    print(f"\n✅ Consolidated review saved to: {output_file}")
    print(f"   Model used: {model}")

    # Also print to stdout for piping
    print("\n" + "=" * 80)
    print(consolidated)


if __name__ == "__main__":
    asyncio.run(main())
