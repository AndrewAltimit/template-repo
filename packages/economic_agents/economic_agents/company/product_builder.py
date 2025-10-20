"""Product builder for developing proof of concepts."""

from economic_agents.company.models import Product, ProductSpec


class ProductBuilder:
    """Builds proof of concept products."""

    def __init__(self, config: dict | None = None):
        """Initialize product builder.

        Args:
            config: Configuration for product building
        """
        self.config = config or {}

    def build_mvp(self, product_spec: ProductSpec) -> Product:
        """Create minimum viable product from specification.

        Args:
            product_spec: Product specification

        Returns:
            Product with MVP status
        """
        # Simulate MVP development
        category = product_spec.category

        if category == "api-service":
            return self._build_api_service_mvp(product_spec)
        elif category == "cli-tool":
            return self._build_cli_tool_mvp(product_spec)
        elif category == "library":
            return self._build_library_mvp(product_spec)
        elif category == "saas":
            return self._build_saas_mvp(product_spec)
        else:
            return self._build_generic_mvp(product_spec)

    def _build_api_service_mvp(self, spec: ProductSpec) -> Product:
        """Build API service MVP."""
        return Product(
            spec=spec,
            status="alpha",
            completion_percentage=70.0,
            code_artifacts={
                "server.py": "FastAPI server implementation",
                "routes.py": "API route definitions",
                "models.py": "Data models",
                "tests.py": "Unit tests",
                "requirements.txt": "Python dependencies",
            },
            documentation="# API Documentation\n\n## Endpoints\n\n"
            "- POST /transform - Transform data\n"
            "- GET /health - Health check\n\n"
            "## Authentication\n\nAPI key required in header.",
            demo_url="https://demo.api-service.local",
        )

    def _build_cli_tool_mvp(self, spec: ProductSpec) -> Product:
        """Build CLI tool MVP."""
        return Product(
            spec=spec,
            status="alpha",
            completion_percentage=65.0,
            code_artifacts={
                "cli.py": "CLI entry point",
                "commands.py": "Command implementations",
                "utils.py": "Helper utilities",
                "tests.py": "Test suite",
                "setup.py": "Package configuration",
            },
            documentation="# CLI Tool Documentation\n\n## Installation\n\n"
            "```bash\npip install tool-name\n```\n\n"
            "## Usage\n\n```bash\ntool-name command --option value\n```",
            demo_url=None,
        )

    def _build_library_mvp(self, spec: ProductSpec) -> Product:
        """Build library MVP."""
        return Product(
            spec=spec,
            status="alpha",
            completion_percentage=60.0,
            code_artifacts={
                "__init__.py": "Package initialization",
                "core.py": "Core functionality",
                "utils.py": "Utility functions",
                "tests.py": "Test suite",
                "README.md": "Documentation",
            },
            documentation="# Library Documentation\n\n## Installation\n\n"
            "```python\nimport library\n```\n\n"
            "## Usage\n\n```python\nlibrary.function(args)\n```",
            demo_url=None,
        )

    def _build_saas_mvp(self, spec: ProductSpec) -> Product:
        """Build SaaS MVP."""
        return Product(
            spec=spec,
            status="development",
            completion_percentage=50.0,
            code_artifacts={
                "frontend/": "React application",
                "backend/": "API server",
                "database/": "Schema definitions",
                "tests/": "Test suites",
                "docker-compose.yml": "Development environment",
            },
            documentation="# SaaS Platform Documentation\n\n## Features\n\n"
            "- User authentication\n"
            "- Dashboard\n"
            "- Core functionality\n\n"
            "## Deployment\n\nDocker-based deployment",
            demo_url="https://demo.saas-product.local",
        )

    def _build_generic_mvp(self, spec: ProductSpec) -> Product:
        """Build generic MVP."""
        return Product(
            spec=spec,
            status="development",
            completion_percentage=55.0,
            code_artifacts={
                "main.py": "Main application",
                "core.py": "Core logic",
                "tests.py": "Tests",
                "README.md": "Documentation",
            },
            documentation=f"# {spec.name} Documentation\n\nBasic MVP implementation.",
            demo_url=None,
        )

    def iterate_product(self, product: Product, iteration_focus: str) -> Product:
        """Iterate on existing product.

        Args:
            product: Existing product
            iteration_focus: Area to focus on ("features", "quality", "performance")

        Returns:
            Updated product
        """
        # Increase completion based on iteration
        product.completion_percentage = min(100.0, product.completion_percentage + 15.0)

        # Update status based on completion
        if product.completion_percentage >= 90:
            product.status = "beta"
        elif product.completion_percentage >= 70:
            product.status = "alpha"
        elif product.completion_percentage >= 50:
            product.status = "development"

        return product

    def generate_demo(self, product: Product) -> str:
        """Generate demo for product.

        Args:
            product: Product to demo

        Returns:
            Demo description
        """
        return f"""
# {product.spec.name} Demo

## Overview
{product.spec.description}

## Status
- Development: {product.status}
- Completion: {product.completion_percentage}%

## Features
{chr(10).join('- ' + f for f in product.spec.features)}

## Tech Stack
{', '.join(product.spec.tech_stack)}

## Demo Access
{product.demo_url or 'Demo not yet available'}
"""
