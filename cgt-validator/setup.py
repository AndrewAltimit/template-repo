from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

# Read core requirements from requirements-core.txt
with open("requirements-core.txt", "r", encoding="utf-8") as f:
    core_requirements = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

setup(
    name="cgt-validator",
    version="0.1.0",
    author="CGT Validator Team",
    description="Health cost growth target data validation tool for multiple US states",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/cgt-validator",
    packages=find_packages(where="src"),
    py_modules=["cli"],
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
            "cgt-monitor=scripts.monitor_templates:main",
            "cgt-check-critical=scripts.check_critical_changes:main",
            "cgt-test-monitoring=scripts.test_template_monitoring:main",
            "cgt-validate-mock=scripts.validate_mock_data:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yaml", "*.json", "*.html", "*.md"],
    },
)
