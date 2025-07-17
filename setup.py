"""Setup script for the Whale Alert package."""
from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="whale_alert",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A Telegram bot that listens to Whale Alert messages and stores them in TimescaleDB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/whale_alert",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "python-dotenv>=1.0.0",
        "telethon>=1.28.5",
        "asyncpg>=0.27.0",
        "sqlalchemy>=2.0.0",
        "alembic>=1.11.0",
        "python-dateutil>=2.8.2",
        "pydantic>=1.10.0",
    ],
    extras_require={
        "dev": [
            "black>=23.3.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
            "pytest>=7.3.1",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "whale-alert=whale_alert.__main__:main",
        ],
    },
)
