#!/usr/bin/env python3
"""One-touch orchestrator for Model A/B Claude Code workflows."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import textwrap
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

sys.path.insert(0, str(SCRIPT_DIR))

from utils import (  # type: ignore  # Imported at runtime for colocated scripts
    get_available_models,
    load_api_key,
    validate_git_repository,
)

AVAILABLE_MODELS = list(get_available_models().keys())


def _python_executable() -> str:
    return sys.executable or "python3"


def _script_path(name: str) -> Path:
    return SCRIPT_DIR / name


def _run_command(description: str, command: list[str], cwd: Path, env: dict[str, str]) -> None:
    banner = f"\n>>> {description}"
    print("=" * len(banner))
    print(banner)
    print("=" * len(banner))
    print("Command:", " ".join(command))

    result = subprocess.run(command, cwd=cwd, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Step failed: {description}. See output above for details.")


def _prompt(message: str) -> None:
    input(f"\n{message}\nPress Enter to continue...")


def _ensure_api_key() -> str:
    api_key = load_api_key()
    if not api_key:
        raise SystemExit(
            textwrap.dedent(
                """
                Anthropic API key is not configured.
                Set the ANTHROPIC_API_KEY environment variable or run:
                  python scripts/configure_api_key.py
                """
            ).strip()
        )
    return api_key


def _build_env(base_env: dict[str, str], api_key: str, dry_run: bool) -> dict[str, str]:
    env = base_env.copy()
    env.setdefault("ANTHROPIC_API_KEY", api_key)
    if dry_run:
        env["CLAUDE_LAUNCH_DISABLED"] = "1"
    return env


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Streamlined Model A/B workflow orchestrator")
    parser.add_argument("task_id", help="Identifier to use for the TASK-* directory")
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Repository root to operate on (default: current working directory)",
    )
    parser.add_argument(
        "--model-a",
        choices=AVAILABLE_MODELS,
        help="Explicit Model A identifier (defaults to random selection).",
    )
    parser.add_argument(
        "--model-b",
        choices=AVAILABLE_MODELS,
        help="Explicit Model B identifier (defaults to opposite model).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip launching claude CLI and create placeholder transcripts instead.",
    )
    parser.add_argument(
        "--skip-prompts",
        action="store_true",
        help="Do not pause between scripts (useful for automated smoke-tests).",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Proceed even if the repository has uncommitted changes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    repo_path = args.repo.resolve()
    if not repo_path.exists():
        raise SystemExit(f"Repository path does not exist: {repo_path}")

    os.chdir(repo_path)
    validate_git_repository()

    api_key = _ensure_api_key()
    env = _build_env(os.environ, api_key, dry_run=args.dry_run)

    script_steps: list[tuple[str, list[str]]] = [
        (
            "Initializing Model A session",
            [_python_executable(), str(_script_path("script1_model_a_init.py")), args.task_id]
            + (["--model-id", args.model_a] if args.model_a else [])
            + (["--allow-dirty"] if args.allow_dirty else []),
        ),
        (
            "Transitioning to Model B",
            [_python_executable(), str(_script_path("script2_model_b_init.py"))]
            + (["--model-id", args.model_b] if args.model_b else []),
        ),
        (
            "Finalizing Model B session",
            [_python_executable(), str(_script_path("script3_model_b_capture.py"))],
        ),
    ]

    reminders = (
        "Document at least 10 meaningful turns per model.",
        "Reuse the exact same starting prompt between models.",
        "Review transcripts for API key strings before uploading.",
    )

    print("\nWorkflow checklist:")
    for item in reminders:
        print(f" • {item}")

    for description, command in script_steps:
        _run_command(description, command, cwd=repo_path, env=env)
        if not args.skip_prompts and description != script_steps[-1][0]:
            _prompt("Confirm the Claude session has completed and transcripts look good.")

    print("\n✅ Workflow complete. Review TASK-* artifacts before uploading.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")

