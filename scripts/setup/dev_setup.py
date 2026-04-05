#!/usr/bin/env python3
"""Development environment setup script.

Run this once after cloning the repository:
    python scripts/setup/dev_setup.py

Or manually:
    pip install -e .
    pip install -e science/
"""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).parent.parent.parent

    print("Setting up Soma development environment...")
    print(f"Root directory: {root}")

    # Install main project in editable mode
    print("\n[1/3] Installing main project dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(root)],
        check=True
    )

    # Install science package in editable mode
    print("\n[2/3] Installing science package...")
    science_path = root / "science"
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(science_path)],
        check=True
    )

    # Install dev dependencies
    print("\n[3/3] Installing dev dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", f"{root}[dev]"],
        check=True
    )

    print("\n" + "=" * 60)
    print("Development environment setup complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Ensure PostgreSQL with TimescaleDB is running")
    print("  2. Run: python scripts/setup/init_db.py")
    print("  3. Start API: uvicorn api.main:app --reload")
    print("  4. Run tests: pytest tests/")


if __name__ == "__main__":
    main()
