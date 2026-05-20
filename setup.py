"""Setup script for NovaPilot."""

import os
import sys
from setuptools import setup, find_packages

# Read the long description from README
here = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(here, "README.md")
if os.path.exists(readme_path):
    with open(readme_path, "r", encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "NovaPilot - Lightweight Terminal AI Personal Super Intelligence Engine"

# Read version from package
version = {}
version_path = os.path.join(here, "novapilot", "__init__.py")
with open(version_path, "r", encoding="utf-8") as f:
    exec(f.read(), version)
version_str = version.get("__version__", "0.1.0")

setup(
    name="novapilot",
    version=version_str,
    description="Lightweight Terminal AI Personal Super Intelligence Engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="NovaPilot Contributors",
    license="MIT",
    python_requires=">=3.8",
    packages=find_packages(exclude=["tests*", "docs*"]),
    entry_points={
        "console_scripts": [
            "novapilot=novapilot.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Environment :: Console",
    ],
    keywords="ai, cli, llm, terminal, chatbot, privacy",
    project_urls={
        "Homepage": "https://github.com/novapilot/novapilot",
        "Bug Tracker": "https://github.com/novapilot/novapilot/issues",
    },
)
