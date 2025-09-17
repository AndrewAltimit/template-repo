"""Setup script for Sleeper Agent Detection package."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="sleeper-detection",
    version="2.0.0",
    author="Andrew Altimit",
    description="Comprehensive evaluation framework for detecting sleeper agents in language models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AndrewAltimit/template-repo",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.10",
    install_requires=[
        "torch>=2.2.0",
        "transformers>=4.35.0",
        "einops>=0.7.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "scikit-learn>=1.3.0",
        "jinja2>=3.1.0",
        "matplotlib>=3.7.0",
        "seaborn>=0.12.0",
        "plotly>=5.17.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "colorama>=0.4.6",
        "tabulate>=0.9.0",
        "tqdm>=4.66.0",
        "aiofiles>=23.2.1",
        "httpx>=0.25.0",
        "psutil>=5.9.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "sleeper-detect=packages.sleeper_detection.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "sleeper_detection": [
            "test_suites/*.yaml",
            "configs/*.json",
            "docs/*.md",
        ],
    },
)
