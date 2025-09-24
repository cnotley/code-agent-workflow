#!/usr/bin/env python3

import argparse
import getpass
import os
import stat
import sys
from pathlib import Path


def _default_key_path() -> Path:
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support" / "claude-code"
    else:
        base = home / ".config" / "claude-code"
    base.mkdir(parents=True, exist_ok=True)
    return base / "api_key"


def _write_key(target_path: Path, api_key: str) -> None:
    target_path.write_text(api_key + "\n", encoding="utf-8")
    try:
        target_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except PermissionError:
        # On some file systems chmod may fail; continue with a warning
        print("⚠️  Could not adjust permissions; please ensure only your user can read the file.")


def configure_key(target_path: Path) -> None:
    print("🔐 Configure Anthropic API key")
    print("   The key will be stored locally and never committed to git.")
    print(f"   Target path: {target_path}")

    existing = os.environ.get("ANTHROPIC_API_KEY")
    if existing:
        print("ℹ️  Detected ANTHROPIC_API_KEY in the environment; this script will still write a local copy.")

    first_entry = getpass.getpass("Enter API key (input hidden): ").strip()
    if not first_entry:
        print("❌ Aborted: empty key provided.")
        return

    second_entry = getpass.getpass("Re-enter API key for confirmation: ").strip()
    if first_entry != second_entry:
        print("❌ Keys did not match. No changes written.")
        return

    _write_key(target_path, first_entry)
    print("✅ API key stored locally.")
    print("   Future runs of the workflow scripts will automatically pick up this key.")
    print("   You can remove or rotate it anytime by re-running this script.")


def main():
    parser = argparse.ArgumentParser(description="Create or update the local Anthropic API key file.")
    parser.add_argument(
        "--path",
        type=Path,
        default=_default_key_path(),
        help="Override location of the API key file (defaults to user config directory).",
    )

    args = parser.parse_args()
    configure_key(args.path)


if __name__ == "__main__":
    main()

