#!/usr/bin/env python3
"""
Shared utility functions for Claude Code annotation scripts.
"""

import os
import re
import json
import uuid
import stat
import sys
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Iterable
SENSITIVE_DIFF_PATTERNS = (
    re.compile(r"sk-(?:ant|live|test)[a-z0-9_-]{10,}", re.IGNORECASE),
    re.compile(r"anthropic[_-]?api[_-]?key", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]", re.IGNORECASE),
)

SNAPSHOT_EXCLUDE_FILENAME = ".snapshot-exclude"


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return f"S{uuid.uuid4().hex[:8]}"


def generate_uuid() -> str:
    """Generate a UUID for the session."""
    return str(uuid.uuid4())


def get_current_timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.utcnow().isoformat() + "Z"


def get_available_models() -> Dict[str, str]:
    """Get the available Claude models for annotation."""
    return {
        "claude-brocade-v22-p": "claude-brocade-v22-p",
        "claude-opus-4-1-20250805": "claude-opus-4-1-20250805"
    }


def select_random_model() -> str:
    """Randomly select a model for Model A."""
    import random
    models = get_available_models()
    return random.choice(list(models.keys()))


def get_opposite_model(model_id: str) -> str:
    """Get the opposite model for Model B given Model A."""
    models = get_available_models()
    for model_name in models.keys():
        if model_name != model_id:
            return model_name
    raise Exception(f"Could not find opposite model for: {model_id}")


def _candidate_api_key_paths() -> Iterable[Path]:
    """Return potential filesystem locations for the Anthropic API key."""
    home = Path.home()

    if sys.platform == "darwin":
        yield home / "Library" / "Application Support" / "claude-code" / "api_key"

    yield home / ".config" / "claude-code" / "api_key"
    yield home / ".claude" / "api_key"


def load_api_key() -> Optional[str]:
    """Return the Anthropic API key from environment or disk, if available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key and api_key.strip():
        return api_key.strip()

    for candidate in _candidate_api_key_paths():
        if candidate.exists():
            try:
                with open(candidate, "r", encoding="utf-8") as handle:
                    key_value = handle.read().strip()
                    if key_value:
                        return key_value
            except OSError:
                continue

    return None


def get_git_commit_hash() -> str:
    """Get the current git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to get git commit hash: {e}")


def reset_git_to_commit(commit_hash: str) -> None:
    """Reset git repository to a specific commit and clean all changes, but preserve annotation scripts."""
    try:
        print(f"🔄 Resetting repository to base commit: {commit_hash}")
        
        # List of annotation scripts to preserve
        script_files = [
            'script1_model_a_init.py',
            'script2_model_b_init.py', 
            'script3_model_b_capture.py',
            'run_workflow.py',
            'configure_api_key.py',
            'set_api_key.sh',
            '.snapshot-exclude',
            'utils.py',
            'README.md'  # In case it's the annotation README
        ]
        
        # Backup annotation scripts to parent directory (outside repo)
        backup_dir = Path("../.annotation_scripts_backup")
        backup_dir.mkdir(exist_ok=True)
        
        for script_file in script_files:
            if Path(script_file).exists():
                shutil.copy2(script_file, backup_dir / script_file)
        
        print("   ✅ Annotation scripts backed up")
        
        # Hard reset to the base commit (removes staged and unstaged changes)
        subprocess.run(
            ["git", "reset", "--hard", commit_hash],
            check=True,
            capture_output=True
        )
        
        # Clean untracked files and directories (removes new files)
        subprocess.run(
            ["git", "clean", "-fd"],
            check=True,
            capture_output=True
        )
        
        # Restore annotation scripts
        print("   🔄 Restoring annotation scripts...")
        for script_file in script_files:
            backup_path = backup_dir / script_file
            if backup_path.exists():
                shutil.copy2(backup_path, script_file)
                print(f"      ✅ Restored {script_file}")
        
        print(f"✅ Repository completely reset to commit: {commit_hash}")
        print("   - All staged changes removed")
        print("   - All modifications reverted") 
        print("   - All new files removed")
        print("   - Annotation scripts preserved")
        print("   - Working directory clean")
        
        # Clean up backup directory
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
            print("   ✅ Backup directory cleaned up")
        
    except subprocess.CalledProcessError as e:
        # Clean up backup directory if it exists
        backup_dir = Path("../.annotation_scripts_backup")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        raise Exception(f"Failed to reset git to commit {commit_hash}: {e}")
    except Exception as e:
        # Clean up backup directory if it exists
        backup_dir = Path("../.annotation_scripts_backup")
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        raise Exception(f"Failed to reset git to commit {commit_hash}: {e}")


def _snapshot_exclude_file() -> Optional[Path]:
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir / SNAPSHOT_EXCLUDE_FILENAME
    return candidate if candidate.exists() else None


def create_code_snapshot(snapshot_path: str) -> None:
    """Create a repository snapshot with a reproducible exclude list."""
    snapshot_dir = Path(snapshot_path)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    print("📦 Creating complete repository snapshot...")

    rsync_cmd = [
        "rsync",
        "-a",
        "--delete",
        "--safe-links",
        "./",
        str(snapshot_dir),
    ]

    exclude_file = _snapshot_exclude_file()
    if exclude_file:
        rsync_cmd.insert(3, f"--exclude-from={exclude_file}")
    else:
        for pattern in (".git", "node_modules", "__pycache__", ".claude", "*.key", "*.pem"):
            rsync_cmd.insert(3, f"--exclude={pattern}")

    try:
        subprocess.run(
            rsync_cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        print("⚠️  rsync not found, falling back to shutil.copytree ...")
        _copytree_with_excludes(snapshot_dir)
    except subprocess.CalledProcessError as exc:
        raise Exception(f"Snapshot creation failed: {exc.stderr or exc}")

    print(f"✅ Complete repository snapshot created at: {snapshot_path}")

    try:
        result = subprocess.run(
            ["find", str(snapshot_dir), "-type", "f"],
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout.strip():
            file_count = len(result.stdout.strip().split("\n"))
            print(f"   📁 {file_count} files captured")
    except subprocess.SubprocessError:
        print("   📁 Repository snapshot completed")


def _copytree_with_excludes(snapshot_dir: Path) -> None:
    exclude_patterns = {".git", "node_modules", "__pycache__", ".claude"}
    script_names = {
        "script1_model_a_init.py",
        "script2_model_b_init.py",
        "script3_model_b_capture.py",
        "utils.py",
    }

    if snapshot_dir.exists():
        shutil.rmtree(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    for item in Path.cwd().iterdir():
        if item.name in exclude_patterns or item.name in script_names:
            continue
        if any(item.match(pattern) for pattern in exclude_patterns):
            continue

        destination = snapshot_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, ignore=shutil.ignore_patterns(*exclude_patterns))
        else:
            shutil.copy2(item, destination)


def _git_command(command: List[str], allow_empty: bool = False) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as exc:
        if allow_empty and exc.returncode == 1 and exc.stdout == "":
            return ""
        raise Exception(
            f"Git command failed ({' '.join(command)}): {exc.stderr or exc.stdout or exc}"
        )


def _filter_diff(diff_contents: str) -> str:
    if not diff_contents.strip():
        return diff_contents

    exclude_tokens = {
        "script1_model_a_init.py",
        "script2_model_b_init.py",
        "script3_model_b_capture.py",
        "utils.py",
        "README.md",
        ".claude/",
        ".snapshot-exclude",
    }

    filtered_lines: List[str] = []
    skip_block = False
    for line in diff_contents.splitlines():
        if line.startswith("diff --git"):
            skip_block = any(token in line for token in exclude_tokens)
        if not skip_block:
            filtered_lines.append(line)

    return "\n".join(filtered_lines) + ("\n" if filtered_lines else "")


def _diff_contains_sensitive_tokens(diff_contents: str) -> bool:
    return any(pattern.search(diff_contents) for pattern in SENSITIVE_DIFF_PATTERNS)


def create_git_diff(output_path: str, base_commit: str) -> None:
    """Create a git diff patch file including tracked and untracked changes."""
    print("📦 Creating git diff from base commit...")

    tracked_diff = _git_command(["git", "diff", "--binary", f"{base_commit}"], allow_empty=True)
    untracked_diff_segments: List[str] = []

    status_output = _git_command(["git", "status", "--porcelain"], allow_empty=True)
    for line in status_output.splitlines():
        if line.startswith("?? "):
            file_path = line[3:].strip()
            if not file_path:
                continue
            diff_segment = _git_command(
                ["git", "diff", "--binary", "--no-index", "--", "/dev/null", file_path],
                allow_empty=True,
            )
            if diff_segment.strip():
                untracked_diff_segments.append(diff_segment)

    combined_diff = "".join([tracked_diff] + untracked_diff_segments)
    filtered_diff = _filter_diff(combined_diff)

    if _diff_contains_sensitive_tokens(filtered_diff):
        raise Exception(
            "Sensitive tokens detected in git diff. Aborting diff generation. "
            "Please remove secrets from the working tree and retry."
        )

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(filtered_diff)

    if filtered_diff.strip():
        change_count = filtered_diff.count("\ndiff --git") or 1
        print(f"✅ Git diff created at: {output_path}")
        print(f"   📊 {change_count} files changed")
    else:
        print(f"ℹ️  No code changes detected; diff saved as empty file at: {output_path}")


def save_session_metadata(session_dir: str, metadata: Dict[str, Any]) -> None:
    """Save session metadata to JSON file."""
    metadata_path = Path(session_dir) / "session_metadata.json"
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Session metadata saved to: {metadata_path}")


def load_session_metadata(session_dir: str) -> Dict[str, Any]:
    """Load session metadata from JSON file."""
    metadata_path = Path(session_dir) / "session_metadata.json"
    
    if not metadata_path.exists():
        raise FileNotFoundError(f"Session metadata not found at: {metadata_path}")
    
    with open(metadata_path, 'r') as f:
        return json.load(f)


def create_session_directory(session_id: str, task_id: str, model_label: str) -> str:
    """Create session directory structure under TASK-<task_id> folder parallel to the repository."""
    # Create task folder with TASK- prefix parallel to current repository
    current_repo = Path.cwd()
    parent_dir = current_repo.parent
    task_dir_name = f"TASK-{task_id}"
    task_dir = parent_dir / task_dir_name
    task_dir.mkdir(exist_ok=True)
    
    # Create session directory with model label (modelA or modelB)
    session_dir_name = f"{session_id}-{model_label}"
    session_dir = task_dir / session_dir_name
    session_dir.mkdir(exist_ok=True)
    
    # Create snapshots subdirectory
    snapshots_dir = session_dir / "snapshots"
    snapshots_dir.mkdir(exist_ok=True)
    
    print(f"✅ Task directory created: {task_dir}")
    print(f"✅ Session directory created: {session_dir}")
    return str(session_dir)






def print_session_summary(session_id: str, model_id: str, base_commit: str) -> None:
    """Print a summary of the session setup."""
    print("\n" + "="*60)
    print(f"SESSION SETUP COMPLETE")
    print("="*60)
    print(f"Session ID: {session_id}")
    print(f"Model ID: {model_id}")
    print(f"Base Commit: {base_commit}")
    print(f"Session Directory: {session_id}/")
    print("="*60)
    print(f"4. Run the next script when ready")
    print("="*60 + "\n")


def validate_git_repository() -> None:
    """Validate that we're in a git repository."""
    if not Path('.git').exists():
        raise Exception("Not in a git repository. Please run this script from the root of your git repository.")


def check_git_status() -> bool:
    """Check if there are uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True
        )
        return len(result.stdout.strip()) > 0
    except subprocess.CalledProcessError:
        return False


def initialize_claude_code(model_id: str, session_id: str) -> bool:
    """
    Initialize Claude Code session with API key and model name only.
    """
    print(f"🚀 Starting Claude Code session...")
    print(f"Model: {model_id}")

    api_key = load_api_key()
    if not api_key:
        print("❌ No Anthropic API key available.")
        print("   Set ANTHROPIC_API_KEY in your shell or run:")
        print("   python scripts/configure_api_key.py")
        return False
    
    # Create transcript log file in the most recent session directory
    current_repo = Path.cwd()
    parent_dir = current_repo.parent
    
    # Find session directories in task folders
    task_dirs = [d for d in parent_dir.iterdir() if d.is_dir() and d.name.startswith('TASK-')]
    session_dirs = []
    
    for task_dir in task_dirs:
        for item in task_dir.iterdir():
            if item.is_dir() and item.name.startswith('S') and ('-modelA' in item.name or '-modelB' in item.name):
                session_dirs.append(item)
    
    if session_dirs:
        # Use the most recent session directory
        session_dir = max(session_dirs, key=lambda d: d.stat().st_mtime)
        transcript_file = session_dir / "claude_transcript.log"
    else:
        # Fallback to current directory
        transcript_file = Path("claude_transcript.log")

    dry_run_flag = os.environ.get("CLAUDE_LAUNCH_DISABLED", "").strip().lower()
    if dry_run_flag in {"1", "true", "yes"}:
        transcript_file.parent.mkdir(parents=True, exist_ok=True)
        transcript_file.write_text(
            "[dry-run] Claude Code session launch skipped. Set CLAUDE_LAUNCH_DISABLED=0 to enable.",
            encoding="utf-8",
        )
        print("⚙️  Dry-run mode enabled; skipping Claude Code launch.")
        print(f"   Placeholder transcript created at: {transcript_file}")
        return True

    if shutil.which("claude") is None:
        print("❌ `claude` binary not found in PATH.")
        print("   Install Claude Code CLI or export CLAUDE_LAUNCH_DISABLED=1 for testing.")
        return False

    # Launch Claude Code and capture output
    try:
        print("🚀 Starting Claude Code...")
        print("💡 After completing your task, exit Claude Code to continue with the next script.")
        print(f"📝 Export the transcript to: {transcript_file}")
        print("\n" + "="*50)
        print("CLAUDE CODE SESSION STARTING")
        print("="*50)
        print(f"Model: {model_id}")
        print("="*50)
        print()
        
        # Start claude command with the environment and capture output
        env = os.environ.copy()
        env["ANTHROPIC_API_KEY"] = api_key
        
        # Use script command to capture terminal session including user input
        claude_cmd = ["claude", "--model", model_id]
        script_cmd = ["script", "-q", str(transcript_file)] + claude_cmd
        
        # Try with script command first (captures full terminal session)
        try:
            result = subprocess.run(
                script_cmd,
                cwd=os.getcwd(),
                env=env
            )
            print(f"✅ Claude Code transcript saved to: {transcript_file}")
        except (FileNotFoundError, subprocess.CalledProcessError):
            # Fallback: run claude directly without transcript capture
            print("⚠️  Script command not available, running claude directly...")
            result = subprocess.run(
                claude_cmd,
                cwd=os.getcwd(),
                env=env
            )
            print("⚠️  Transcript capture not available - please manually save conversation if needed")
        
        print("\n" + "="*50)
        print("CLAUDE CODE SESSION ENDED")
        print("="*50)
        print("✅ Claude Code session completed!")
        print("🔄 Ready to proceed to next step...")
        print("="*50)
        
        return True
        
    except FileNotFoundError:
        print("❌ Error: `claude` command not found in PATH")
        print("\nFallback: Run these commands manually:")
        print(f"  cd {os.getcwd()}")
        print(f"  script {transcript_file} claude --model {model_id}  # (captures transcript)")
        print(f"  # OR just: claude --model {model_id}  # (no transcript)")
        return False
        
    except KeyboardInterrupt:
        print("\n⚠️  Claude Code session interrupted by user")
        return True
        
    except Exception as e:
        print(f"❌ Error starting Claude Code: {e}")
        print("\nFallback: Run these commands manually:")
        print(f"  cd {os.getcwd()}")
        print(f"  script {transcript_file} claude --model {model_id}  # (captures transcript)")
        return False


def wait_for_claude_session_start(session_id: str, timeout: int = 30) -> bool:
    """
    Wait for Claude Code session to start by checking for session indicators.
    """
    print(f"⏳ Waiting for Claude Code session to start (timeout: {timeout}s)...")
    
    import time
    start_time = time.time()
    
    # Look for indicators that Claude Code session has started
    session_indicators = [
        f".claude_session_{session_id}.lock",
        ".cursor/claude_active",
        ".vscode/claude_active",
        "claude_session.log"
    ]
    
    while time.time() - start_time < timeout:
        for indicator in session_indicators:
            if Path(indicator).exists():
                print(f"✅ Claude Code session detected via: {indicator}")
                return True
        
        time.sleep(1)
    
    print("⚠️  Could not detect Claude Code session start automatically")
    print("Please ensure Claude Code is running before proceeding")
    return False


def create_claude_prompt_file(session_dir: str, task_id: str) -> str:
    """
    Create a prompt template file for the user to use in Claude Code.
    """
    prompt_file = Path(session_dir) / "task_prompt.txt"
    current_repo = Path.cwd().name
    
    prompt_template = f"""# Task ID: {task_id}

## Instructions
Paste your task prompt below this line, then copy the entire content to Claude Code:

---

[PASTE YOUR TASK PROMPT HERE]

---

## Session Info
- Task ID: {task_id}
- Repository: {current_repo}
- Session Directory: {session_dir}
- Timestamp: {get_current_timestamp()}

## Notes
- This file is for reference only
- Copy the prompt section to Claude Code
- Complete the task as requested
- Do not commit changes until instructed by the next script
- Session data is saved parallel to your repository
"""
    
    with open(prompt_file, "w") as f:
        f.write(prompt_template)
    
    print(f"📝 Prompt template created: {prompt_file}")
    return str(prompt_file)

def extract_claude_transcript_data(file_path: str):
    """
    Extract human inputs, AI responses, and tool calls from Claude transcript files.
    Handles ANSI escape sequences, multi-line prompts, and long responses.
    Returns ordered transcript with role and content, including separate tool_call role.
    """
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Step 1: Clean ANSI escape codes and terminal control sequences
    # Remove actual ANSI escape sequences (with \x1B prefix)
    cleaned_content = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', content)
    
    # Remove literal ANSI code strings that appear as text in transcripts
    terminal_patterns = [
        r'\[\?[0-9]+[hl]',  # DEC private mode sequences like [?25l, [?2004h
        r'\[38;2;[0-9]+;[0-9]+;[0-9]+m',  # RGB color codes like [38;2;215;119;87m
        r'\[39m|\[49m',  # Reset foreground/background color
        r'\[1m|\[22m|\[2m|\[23m|\[3m|\[4m|\[24m|\[7m|\[27m',  # Text formatting toggles
        r'\[[0-9]+m',  # Simple color codes
        r'\[[0-9;]+m',  # Multiple parameter color codes
        r'\]0;[^\\]*\\',  # Window title sequences
    ]
    
    for pattern in terminal_patterns:
        cleaned_content = re.sub(pattern, '', cleaned_content)
    
    # Remove control characters and special Unicode symbols
    cleaned_content = re.sub(r'[\x00-\x08\x0B-\x1F\x7F-\x9F]', '', cleaned_content)
    cleaned_content = re.sub(r'[╭╮│╰╯─═║┌┐└┘├┤┬┴┼]', '', cleaned_content)  # Box drawing
    # Note: ⎿ is a tool result marker, not decorative - keep it!
    cleaned_content = re.sub(r'\(B', '', cleaned_content)  # Terminal artifacts
    
    # Clean up excessive whitespace
    cleaned_content = re.sub(r'  +', ' ', cleaned_content)
    cleaned_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned_content)
    
    # Step 2: Split content into lines for processing
    lines = cleaned_content.split('\n')
    
    # Step 3: Extract interactions using improved logic
    transcript = []
    # Enhanced status pattern to filter out tool operation noise
    status_pattern = r'(\.\.\.|\…|ing…|ing\.\.\.|esc to interrupt|Forging|Transfiguring|Ideating|Combobulating|Crunching|Accomplishing|Waiting|Running|Total cost|Total duration|Usage by model|ctrl\+o to expand|\(.+\s+tokens\)|\(.+\s+lines\)|Found \d+ files|Found \d+ lines|Found \d+ matches|No content|Error:|Done \(|\.\.\. \+\d+ lines)'
    
    seen_interactions = set()
    current_human = []
    current_ai = []
    current_tool_call = None
    tool_calls = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Human input (starts with >)
        if line.startswith('> '):
            # Save any pending AI content first
            if current_ai:
                ai_text = ' '.join(current_ai).strip()
                if len(ai_text) > 10 and not re.search(status_pattern, ai_text):
                    if ai_text not in seen_interactions:
                        transcript.append({"role": "agent", "content": ai_text})
                        seen_interactions.add(ai_text)
                current_ai = []
            
            # Start collecting human input
            current_human = [line[2:].strip()]
            
        # AI response or tool call (starts with ⏺ or other symbols) - check this first!
        elif re.match(r'^[⏺✻·✽✶✳✢]\s', line):
            # Save any pending human content first
            if current_human:
                human_text = ' '.join(current_human).strip()
                if len(human_text) > 1:
                    if human_text not in seen_interactions:
                        transcript.append({"role": "human", "content": human_text})
                        seen_interactions.add(human_text)
                current_human = []  # Clear human content
            
            # Save any pending tool call first
            if current_tool_call:
                tool_calls.append(current_tool_call)
                if current_tool_call['content'] not in seen_interactions:
                    transcript.append({"role": "tool_call", "content": current_tool_call['content']})
                    seen_interactions.add(current_tool_call['content'])
                current_tool_call = None
            
            # Extract content (remove the symbol prefix)
            content = re.sub(r'^[⏺✻·✽✶✳✢]\s*', '', line).strip()
            if len(content) > 5 and not re.search(status_pattern, content):
                # Check if this is a tool call (has parentheses with parameters)
                tool_match = re.match(r'^(\w+)\(([^)]*)\)$', content)
                if tool_match:
                    # This is a tool call
                    tool_name = tool_match.group(1)
                    parameters = tool_match.group(2)
                    current_tool_call = {
                        'tool_name': tool_name,
                        'parameters': parameters,
                        'output': '',
                        'content': f"{tool_name}({parameters})"
                    }
                else:
                    # This is regular AI narrative
                    current_ai.append(content)
                
        # Tool result (starts with ⎿) - always part of current tool call
        elif line.strip().startswith('⎿') and current_tool_call:
            # Tool result continuation
            result_content = line.strip()[1:].strip()  # Remove ⎿ and whitespace
            if current_tool_call['output']:
                current_tool_call['output'] += '\n' + result_content
            else:
                current_tool_call['output'] = result_content
            current_tool_call['content'] = f"{current_tool_call['tool_name']}({current_tool_call['parameters']}) → {result_content[:100]}{'...' if len(result_content) > 100 else ''}"
                
        # Continuation of human input (indented lines or plain lines after a human prompt)
        elif current_human and (line.startswith('  ') or 
                               (not line.startswith('>') and 
                                not re.match(r'^[⏺✻·✽✶✳✢]', line) and
                                not line.strip().startswith('⎿') and
                                not current_ai and  # Only if we're not in an AI response
                                len(line) > 3)):
            current_human.append(line.strip())
                
        # Continuation of AI response (plain text lines)
        elif (current_ai and 
              not line.startswith('>') and 
              not re.match(r'^[⏺✻·✽✶✳✢]', line) and
              not line.strip().startswith('⎿') and
              not re.search(status_pattern, line) and
              len(line) > 3):
            current_ai.append(line)
    
    # Handle any remaining content
    if current_human:
        human_text = ' '.join(current_human).strip()
        if len(human_text) > 1:
            if human_text not in seen_interactions:
                transcript.append({"role": "human", "content": human_text})
    
    if current_tool_call:
        tool_calls.append(current_tool_call)
        if current_tool_call['content'] not in seen_interactions:
            transcript.append({"role": "tool_call", "content": current_tool_call['content']})
    
    if current_ai:
        ai_text = ' '.join(current_ai).strip()
        if len(ai_text) > 10 and not re.search(status_pattern, ai_text):
            if ai_text not in seen_interactions:
                transcript.append({"role": "agent", "content": ai_text})
    
    # Legacy format for backward compatibility
    human_inputs = [item["content"] for item in transcript if item["role"] == "human"]
    ai_responses = [item["content"] for item in transcript if item["role"] == "agent"]
    
    return {
        'transcript': transcript,
        'human_inputs': human_inputs,
        'ai_responses': ai_responses,
        'tool_calls': tool_calls,
        'human_count': len(human_inputs),
        'ai_count': len(ai_responses),
        'tool_call_count': len(tool_calls)
    }
