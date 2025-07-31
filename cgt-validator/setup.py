from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read core requirements only (not development/optional packages)
core_requirements = [
    "click>=8.0.0",
    "openpyxl>=3.0.0",
    "pandas>=2.0.0",
    "pyyaml>=6.0.0",
    "jsonschema>=4.0.0",
    "beautifulsoup4>=4.12.0",
    "requests>=2.31.0",
    "lxml>=4.9.0",
    "jinja2>=3.1.0",
    "markdown>=3.5.0",
    "python-dateutil>=2.8.0",
    "tqdm>=4.65.0",
    "tabulate>=0.9.0",
    "colorama>=0.4.6",
    "PyPDF2>=3.0.0",
    "pdfplumber>=0.9.0",
    "tabula-py>=2.8.0",
]

setup(
    name="cgt-validator",
    version="0.1.0",
    author="CGT Validator Team",
    description="Health cost growth target data validation tool for multiple US states",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/cgt-validator",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Healthcare Industry",
        "Topic :: Office/Business :: Financial :: Accounting",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=core_requirements,
    entry_points={
        "console_scripts": [
            "cgt-validate=cli:main",
            "cgt-scrape=scrapers.web_scraper:scrape_state",
            "cgt-scheduler=scrapers.scheduler:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.json", "*.html", "*.md"],
    },
)
