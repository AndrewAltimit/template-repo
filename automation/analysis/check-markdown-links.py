#!/usr/bin/env python3
"""Direct markdown link checker using the shared module"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path to import from tools
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.cli.utilities.markdown_link_checker import MarkdownLinkChecker  # noqa: E402


def format_results_text(results):
    """Format results as human-readable text"""
    output = []

    if not results.get("success"):
        output.append(f"❌ Error: {results.get('error', 'Unknown error')}")
        return "\n".join(output)

    output.append("# Link Check Results\n")
    output.append(f"Files checked: {results.get('files_checked', 0)}")
    output.append(f"Total links: {results.get('total_links', 0)}")
    output.append(f"Broken links: {results.get('broken_links', 0)}\n")

    if results.get("all_valid"):
        output.append("✅ All links are valid!")
    else:
        output.append("❌ Found broken links:\n")

        for file_result in results.get("results", []):
            if file_result.get("broken_count", 0) > 0:
                output.append(f"\n## {file_result.get('file')}")
                output.append(f"   Broken: {file_result.get('broken_count')} / {file_result.get('total_count')}")

                for link_info in file_result.get("links", []):
                    if not link_info.get("valid"):
                        output.append(f"   ✖ {link_info.get('url')}")
                        if link_info.get("error"):
                            output.append(f"     Error: {link_info.get('error')}")

    return "\n".join(output)


def format_results_github(results):
    """Format results as GitHub Actions summary markdown"""
    output = []

    if not results.get("success"):
        output.append(f"## ❌ Link Check Failed\n\n{results.get('error', 'Unknown error')}")
        return "\n".join(output)

    output.append("## Link Check Results\n")
    output.append(f"- **Files checked**: {results.get('files_checked', 0)}")
    output.append(f"- **Total links**: {results.get('total_links', 0)}")
    output.append(f"- **Broken links**: {results.get('broken_links', 0)}\n")

    if results.get("all_valid"):
        output.append("### ✅ All links are valid!")
    else:
        output.append("### ❌ Found broken links\n")

        for file_result in results.get("results", []):
            if file_result.get("broken_count", 0) > 0:
                output.append(f"#### `{file_result.get('file')}`")
                output.append(f"Broken: {file_result.get('broken_count')} / {file_result.get('total_count')}\n")
                output.append("```")

                for link_info in file_result.get("links", []):
                    if not link_info.get("valid"):
                        output.append(f"✖ {link_info.get('url')}")
                        if link_info.get("error"):
                            output.append(f"  → {link_info.get('error')}")

                output.append("```\n")

    return "\n".join(output)


def write_github_outputs(results):
    """Write outputs to GITHUB_OUTPUT if running in GitHub Actions"""
    if "GITHUB_OUTPUT" in os.environ:
        broken_links = results.get("broken_links", 0)
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"total_errors={broken_links}\n")
            f.write(f"failed_files={broken_links}\n")  # For backward compatibility
            f.write(f"files_found={results.get('files_checked', 0)}\n")
            f.write(f"all_valid={'true' if results.get('all_valid', False) else 'false'}\n")


async def main():
    parser = argparse.ArgumentParser(description="Check markdown links")
    parser.add_argument("path", help="Path to markdown file or directory")
    parser.add_argument("--internal-only", action="store_true", help="Only check internal links")
    parser.add_argument(
        "--format",
        choices=["text", "json", "github"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Timeout for HTTP requests in seconds (default: 10)",
    )
    parser.add_argument("--output", help="Output file (default: stdout)")

    args = parser.parse_args()

    # Create checker and run
    checker = MarkdownLinkChecker()
    results = await checker.check_markdown_links(
        path=args.path,
        check_external=not args.internal_only,
        timeout=args.timeout,
    )

    # Format output
    if args.format == "json":
        output = json.dumps(results, indent=2)
    elif args.format == "github":
        output = format_results_github(results)
    else:
        output = format_results_text(results)

    # Write output
    if args.output:
        Path(args.output).write_text(output)
        print(f"Results written to {args.output}")
    else:
        print(output)

    # Write GitHub Actions outputs if applicable
    write_github_outputs(results)

    # Exit with error code if broken links found
    if not results.get("success") or results.get("broken_links", 0) > 0:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
