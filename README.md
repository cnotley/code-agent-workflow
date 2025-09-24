# Claude Code Annotation Scripts

This repository contains three scripts designed for annotator experts to work on the same task with two different Claude models, enabling comparative evaluation and richer annotation data collection.

## Overview

The workflow allows experts to:
1. Work on the same task with two different Claude models (A and B)
2. Capture complete session data including code snapshots, git diffs, and transcripts
3. Generate structured data for evaluation and comparison

## Files

- `run_workflow.py` - One-touch orchestrator that executes the full workflow
- `script1_model_a_init.py` - Initialize Model A session (supports `--model-id` override)
- `script2_model_b_init.py` - Transition from Model A to Model B (supports `--model-id` override)
- `script3_model_b_capture.py` - Finalize Model B session
- `configure_api_key.py` & `set_api_key.sh` - Utilities for storing the Anthropic key locally (never in git)
- `utils.py` - Shared utility functions
- `README.md` - This documentation

## Prerequisites

1. **Git Repository**: Scripts must be run from the root of a git repository
2. **Python 3.9+**: All scripts require Python 3.9 or higher
3. **Claude Code**: Access to the Claude Code CLI (`CLAUDE_LAUNCH_DISABLED=1` allows local dry-runs)
4. **Git**: Command-line git tools installed
5. **rsync**: Used for snapshot creation (falls back automatically if unavailable)
6. **OS**: macOS or Linux

## Installation

1. Clone or download these scripts to your project repository.
2. Store your Anthropic API key locally (never commit it):
```bash
python scripts/configure_api_key.py
```
   *The helper writes the key to `~/Library/Application Support/claude-code/api_key` on macOS or `~/.config/claude-code/api_key` on Linux with user-only permissions.*

## Workflow

### Recommended: use `run_workflow.py`

The orchestrator wraps the three scripts, pauses between Model A and Model B so you can verify transcripts, and guards against accidentally running them out of order.

```bash
python scripts/run_workflow.py TASK_ID --repo /path/to/your/repo \
  [--model-a MODEL_NAME] [--model-b MODEL_NAME] [--dry-run]
```

- `--dry-run` sets `CLAUDE_LAUNCH_DISABLED=1`, generating placeholder transcripts without launching the `claude` binary—handy for smoke-testing on machines that lack Claude Code.
- Use `--skip-prompts` in CI-style automation to avoid pause prompts.

You can continue to run the scripts manually if preferred; the following sections describe that flow.

### Step 1: Initialize Model A Session

Run the first script to set up the initial session:

```bash
python script1_model_a_init.py TASK_ID [--model-id MODEL_NAME]
```

**What it does:**
- Creates a unique session ID (e.g., `S1a2b3c4d`)
- Records the current git commit as the base commit
- Takes a "before" code snapshot
- Sets up session metadata for Model A
- Creates session directory structure
- **Initializes Claude Code session for Model A**
- Creates task prompt template file

**Output:**
```
TASK-T123/                           # Task directory
└── S1a2b3c4d-modelA/               # Model A session directory
    ├── session_metadata.json
    ├── claude_transcript.log
    └── snapshots/
        ├── before_code_state/
        ├── after_code_state/       (empty, filled later)
        └── git_diff.patch          (empty, filled later)
```

### Step 2: Work with Model A

1. **Claude Code should launch automatically** 
2. **Add your task prompt** to the template file
3. **Complete the task** with Model A
4. **Let Claude Code finish** all its work
5. **Do not commit changes** - leave them in working directory

### Step 3: Transition to Model B

Run the second script to capture Model A results and prepare for Model B:

```bash
python script2_model_b_init.py [--model-id MODEL_NAME]
```

**What it does:**
- Captures final state of Model A session (after snapshot, git diff)
- Attempts to copy Claude Code transcript
- Resets git repository to the base commit (clean slate)
- Creates new session for Model B
- **Initializes Claude Code session for Model B**
- Creates fresh task prompt template
- Preserves all Model A data

**Output:**
```
TASK-T123/                          # Task directory
├── S1a2b3c4d-modelA/              # Model A Session (Complete)
│   ├── session_metadata.json
│   ├── claude_transcript.log
│   └── snapshots/
│       ├── before_code_state/
│       ├── after_code_state/
│       └── git_diff.patch
└── S5e6f7g8h-modelB/              # Model B Session (Ready)
    ├── session_metadata.json
    └── snapshots/
        ├── before_code_state/
        ├── after_code_state/      (empty, filled later)
        └── git_diff.patch         (empty, filled later)
```

### Step 4: Work with Model B

1. **Claude Code should launch automatically** (fresh session)
2. **Repository has been reset** to the base commit (clean slate)
3. **Use the SAME task prompt** as Model A 
4. **Copy and paste the prompt** into Claude Code
5. **Complete the task** with Model B
6. **Let Claude Code finish** all its work

### Step 5: Finalize Model B Session

Run the third script to capture Model B results:

```bash
python script3_model_b_capture.py
```

**What it does:**
- Captures final state of Model B session
- Attempts to copy Claude Code transcript
- Creates final git diff
- Generates workflow summary
- Provides Airtable logging information

**Final Output:**
```
TASK-T123/                          # Task directory
├── S1a2b3c4d-modelA/              # Model A Session (Complete)
│   ├── session_metadata.json
│   ├── claude_transcript.log
│   └── snapshots/
│       ├── before_code_state/
│       ├── after_code_state/
│       └── git_diff.patch
└── S5e6f7g8h-modelB/              # Model B Session (Complete)
    ├── session_metadata.json
    ├── claude_transcript.log
    └── snapshots/
        ├── before_code_state/
        ├── after_code_state/
        └── git_diff.patch
```

## Data Structure

Each session generates a JSON metadata file with the following structure:

```json
{
  "task_id": "T123",
  "session_id": "S1a2b3c4d",
  "uuid": "a1b2c3d4-e5f6-7890",
  "base_commit": "abcd1234efgh5678",
  "total_duration": 245,
  "total_cost": null,
  "total_code_changes": 12,
  "model_id": "A",
  "timestamp_start": "2025-09-20T10:15:00Z",
  "timestamp_end": "2025-09-20T10:19:05Z",
  "snapshot_paths": {
    "before": "S1a2b3c4d/snapshots/before_code_state/",
    "after": "S1a2b3c4d/snapshots/after_code_state/",
    "diff": "S1a2b3c4d/snapshots/git_diff.patch"
  },
  "transcript": [],
  "script_version": "1.0",
  "workflow_stage": "model_a_complete"
}
```
Note: The transcript key contains parsed conversation data with categorized human and agent messages that experts can review to verify correct transcript parsing and message classification.

## File Management

### Session Directories
- Each model gets its own session directory (e.g., `S1a2b3c4d/`, `S5e6f7g8h/`)
- Session IDs are unique and generated automatically
- Directory structure is consistent across all sessions

### Snapshots
- `before_code_state/`: Complete copy of repository before any changes
- `after_code_state/`: Complete copy of repository after model completion
- `git_diff.patch`: Git diff from base commit to final state

### Transcripts
- Scripts attempt to automatically locate and copy Claude Code transcripts
- If automatic detection fails, manual copying may be required
- Transcript location may vary depending on Claude Code implementation

## Troubleshooting

### Common Issues

**"Not in a git repository"**
- Ensure you're running scripts from the root of a git repository
- Initialize git if needed: `git init`

**"No Model A session found"**
- Run Script 1 first before Script 2
- Check for `.current_session_a.json` file

**"Claude transcript not found"**
- Transcript auto-detection may fail
- Manually copy transcript to session folder as `transcript_log.json`

**"Uncommitted changes detected"**
- Script 1 warns about uncommitted changes
- Choose to continue (y) or commit/stash changes first


### Manual Transcript Copying

If automatic transcript detection fails:

1. Locate your Claude Code transcript file
2. Copy it to the session folder:
```bash
cp /path/to/claude/transcript.json S1a2b3c4d/transcript_log.json
```

### Recovery

If a script fails mid-execution:

1. **Check session directories** - partial data may be saved
2. **Check git status** - you may need to reset manually
3. **Remove tracking files** - delete `.current_session_*.json` files
4. **Start over** - run Script 1 again if needed

## Data Submission

### Google Drive Upload

1. **Upload the entire task folder** to the designated Google Drive location:
   
   **📤 Upload Link**: https://drive.google.com/drive/folders/1xZom5X3iCFjVcQzsXJfuJw96RGWpkowd?usp=drive_link

2. **Upload the complete TASK-{id}/ directory** (maintains structure with both sessions)
3. **Note the Drive URL** of the uploaded task folder for Airtable logging

### Airtable Logging

Record the following information in Airtable:

- **Task ID**: From command line argument (e.g., T123, 15, AUTH_FEATURE)
- **Prompt Text**: The task prompt you used
- **Base Commit**: Git commit hash (from session metadata)
- **Model A ID**: Model used for first session (e.g., claude-baize-v19-p)
- **Model B ID**: Model used for second session (e.g., claude-opus-4-1-20250805)
- **Model A Session ID**: First session ID
- **Model B Session ID**: Second session ID
- **Drive Link**: URL to uploaded TASK-{id}/ folder
- **Run Timestamps**: Start/end times from metadata
- **Duration**: Total time for each session
- **Code Changes**: Number of files modified
- **Turns**: Number of conversation turns for each session

## Advanced Usage

### Custom Model IDs

You can specify custom model identifiers:

```bash
python script1_model_a_init.py T123 --model-id "claude-3-opus"
python script2_model_b_init.py --model-id "claude-3-sonnet"
```

### Multiple Tasks

For multiple tasks, run the complete workflow for each:

```bash
# Task 1
python script1_model_a_init.py T123
# ... complete Model A work ...
python script2_model_b_init.py
# ... complete Model B work ...
python script3_model_b_capture.py

# Task 2
python script1_model_a_init.py T124
# ... repeat workflow ...
```

## Support

If you encounter issues:

1. **Check this README** for troubleshooting steps
2. **Verify prerequisites** (git, Python, file permissions)
3. **Check script output** for specific error messages
4. **Contact the development team** with error details and context

---

**Version**: 1.0  
**Last Updated**: September 2025  
**Compatibility**: Python 3.6+, Git 2.0+
