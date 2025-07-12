#!/usr/bin/env python3
"""
Example: Complete workflow using multiple MCP tools
This demonstrates a full development workflow including:
- Code quality checks
- AI consultation
- Documentation generation
- Visualization creation
"""

import json
import time
from typing import Any, Dict

import requests


class MCPWorkflow:
    """Orchestrate multiple MCP tools in a workflow"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    def execute_tool(self, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single MCP tool"""
        url = f"{self.base_url}/tools/execute"
        response = requests.post(url, json={"tool": tool, "arguments": arguments})

        if response.status_code == 200:
            return response.json()
        else:
            return {"success": False, "error": f"HTTP {response.status_code}"}

    def log_step(self, step: str, status: str = "INFO"):
        """Log workflow step"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        icon = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}.get(
            status, ""
        )
        print(f"[{timestamp}] {icon} {step}")

    def run_code_quality_workflow(self, code_path: str) -> Dict[str, Any]:
        """Run code quality checks workflow"""
        self.log_step("Starting Code Quality Workflow")
        results = {}

        # Step 1: Format check
        self.log_step("Running format check...")
        format_result = self.execute_tool(
            "format_check", {"path": code_path, "language": "python"}
        )
        results["format_check"] = format_result

        if format_result.get("success") and format_result.get("result", {}).get(
            "formatted"
        ):
            self.log_step("Code is properly formatted", "SUCCESS")
        else:
            self.log_step("Code formatting issues detected", "WARNING")

        # Step 2: Lint
        self.log_step("Running linter...")
        lint_result = self.execute_tool("lint", {"path": code_path})
        results["lint"] = lint_result

        if lint_result.get("success"):
            issues = lint_result.get("result", {}).get("issues", [])
            if issues:
                self.log_step(f"Found {len(issues)} linting issues", "WARNING")
            else:
                self.log_step("No linting issues found", "SUCCESS")

        # Step 3: Get AI recommendations
        self.log_step("Consulting AI for code review...")
        ai_result = self.execute_tool(
            "consult_gemini",
            {
                "question": "Review this code quality report and suggest improvements",
                "context": json.dumps(results, indent=2),
            },
        )
        results["ai_review"] = ai_result

        return results

    def generate_documentation_workflow(
        self, project_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate project documentation"""
        self.log_step("Starting Documentation Generation Workflow")
        results = {}

        # Step 1: Generate LaTeX documentation
        self.log_step("Creating technical documentation...")

        latex_content = self._create_documentation_latex(project_info)
        doc_result = self.execute_tool(
            "compile_latex", {"content": latex_content, "format": "pdf"}
        )
        results["documentation"] = doc_result

        if doc_result.get("success"):
            self.log_step("Documentation generated successfully", "SUCCESS")

        # Step 2: Create architecture visualization
        self.log_step("Creating architecture diagram...")

        manim_script = self._create_architecture_animation(project_info)
        viz_result = self.execute_tool(
            "create_manim_animation", {"script": manim_script, "output_format": "mp4"}
        )
        results["visualization"] = viz_result

        if viz_result.get("success"):
            self.log_step("Architecture visualization created", "SUCCESS")

        return results

    def _create_documentation_latex(self, project_info: Dict[str, Any]) -> str:
        """Create LaTeX documentation template"""
        return rf"""
\documentclass{{article}}
\usepackage{{hyperref}}
\usepackage{{listings}}

\title{{{project_info.get('name', 'Project')} Documentation}}
\author{{{project_info.get('author', 'MCP Workflow')}}}
\date{{\today}}

\begin{{document}}

\maketitle

\section{{Overview}}
{project_info.get('description', 'Project description here.')}

\section{{Architecture}}
{project_info.get('architecture', 'Architecture details here.')}

\section{{API Reference}}
{project_info.get('api', 'API documentation here.')}

\section{{Getting Started}}
\begin{{lstlisting}}[language=bash]
# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
\end{{lstlisting}}

\end{{document}}
        """

    def _create_architecture_animation(self, project_info: Dict[str, Any]) -> str:
        """Create Manim animation script for architecture"""
        return """
from manim import *

class ArchitectureDiagram(Scene):
    def construct(self):
        # Title
        title = Text("System Architecture", font_size=48)
        title.to_edge(UP)
        self.play(Write(title))

        # Create components
        api_box = Rectangle(width=3, height=2, color=BLUE)
        api_text = Text("API Gateway", font_size=24)
        api_group = VGroup(api_box, api_text)

        mcp_box = Rectangle(width=3, height=2, color=GREEN)
        mcp_text = Text("MCP Server", font_size=24)
        mcp_group = VGroup(mcp_box, mcp_text)

        tools_box = Rectangle(width=3, height=2, color=ORANGE)
        tools_text = Text("Tools", font_size=24)
        tools_group = VGroup(tools_box, tools_text)

        # Position components
        api_group.shift(UP * 1.5)
        mcp_group.shift(DOWN * 0.5)
        tools_group.shift(DOWN * 2.5)

        # Create connections
        arrow1 = Arrow(api_group.get_bottom(), mcp_group.get_top())
        arrow2 = Arrow(mcp_group.get_bottom(), tools_group.get_top())

        # Animate
        self.play(Create(api_group))
        self.play(Create(arrow1))
        self.play(Create(mcp_group))
        self.play(Create(arrow2))
        self.play(Create(tools_group))

        self.wait(2)
        """


def main():
    """Run example workflows"""
    print("🚀 MCP Full Workflow Example")
    print("=" * 60)

    workflow = MCPWorkflow()

    # Example 1: Code Quality Workflow
    print("\n📊 Example 1: Code Quality Workflow")
    print("-" * 60)

    quality_results = workflow.run_code_quality_workflow(".")

    print("\nResults Summary:")
    for tool, result in quality_results.items():
        if result.get("success"):
            print(f"  ✅ {tool}: Success")
        else:
            print(f"  ❌ {tool}: Failed - {result.get('error')}")

    # Example 2: Documentation Generation Workflow
    print("\n📚 Example 2: Documentation Generation Workflow")
    print("-" * 60)

    project_info = {
        "name": "MCP Template Project",
        "author": "Development Team",
        "description": (
            "A comprehensive template for MCP-enabled projects "
            "with self-hosted runners."
        ),
        "architecture": (
            "Microservices architecture with Docker containers " "and MCP tools."
        ),
        "api": "RESTful API with comprehensive tool endpoints.",
    }

    doc_results = workflow.generate_documentation_workflow(project_info)

    print("\nResults Summary:")
    for task, result in doc_results.items():
        if result.get("success"):
            output = result.get("result", {}).get("output_path", "N/A")
            print(f"  ✅ {task}: Success - Output: {output}")
        else:
            print(f"  ❌ {task}: Failed")

    # Example 3: Combined AI-Assisted Workflow
    print("\n🤖 Example 3: AI-Assisted Development Workflow")
    print("-" * 60)

    # Step 1: Ask AI for project structure recommendations
    workflow.log_step("Getting AI recommendations for project structure...")

    ai_structure = workflow.execute_tool(
        "consult_gemini",
        {
            "question": (
                "What's the best project structure for a Python "
                "microservice with MCP integration?"
            ),
            "context": (
                "The service needs to handle HTTP requests, "
                "execute MCP tools, and maintain state."
            ),
        },
    )

    if ai_structure.get("success"):
        workflow.log_step("AI recommendations received", "SUCCESS")
        print("\nAI Recommendation (excerpt):")
        print(ai_structure.get("result", {}).get("response", "")[:300] + "...")

    # Step 2: Generate implementation based on AI suggestions
    workflow.log_step("Generating code based on AI recommendations...")

    # This would normally generate actual code files
    workflow.log_step("Code generation completed", "SUCCESS")

    # Step 3: Run quality checks on generated code
    workflow.log_step("Running quality checks on generated code...")

    # This would run the quality workflow on the generated code
    workflow.log_step("Quality checks completed", "SUCCESS")

    print("\n" + "=" * 60)
    print("✨ All workflows completed successfully!")
    print("\nThis example demonstrates:")
    print("  • Code quality checking with format and lint tools")
    print("  • AI-powered code review and recommendations")
    print("  • Automated documentation generation")
    print("  • Visual architecture diagrams with Manim")
    print("  • Orchestration of multiple MCP tools")


if __name__ == "__main__":
    main()
