"""
Setup configuration for transaction-classifier-toolkit
"""

from setuptools import setup, find_packages
from pathlib import Path

readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding='utf-8') if readme_file.exists() else ""

setup(
    name="transaction-classifier-toolkit",
    version="1.0.0",
    author="Silv MT Holdings",
    author_email="",
    description="Transaction classification toolkit - Identifies revenue types, MCA payments, wire types, and deposit categories",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/silv-mt-holdings/transaction-classifier-toolkit",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Financial and Insurance Industry",
        "Topic :: Office/Business :: Financial",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "bankstatement-parser-toolkit",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["data/*.json"],
    },
)
