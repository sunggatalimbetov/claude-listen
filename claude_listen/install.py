"""Set up `/listen` for Claude Code in iTerm2.

- Adds an iTerm2 profile "Listen" used for the reading pane (closes when done).
- Adds a Claude Code slash command `/listen` (~/.claude/commands/listen.md).

Run with: listen --install
"""

import json
import shutil
import sys
from pathlib import Path

PROFILES = Path.home() / "Library" / "Application Support" / "iTerm2" / "DynamicProfiles"
COMMAND = Path.home() / ".claude" / "commands" / "listen.md"

COMMAND_BODY = """---
description: Listen to Claude's last reply (opens a pane with word highlighting)
allowed-tools: Bash(listen:*)
---
!`listen`

Reply with only the word: ok
"""


def install():
    if not shutil.which("listen"):
        sys.exit("`listen` is not on PATH. Install it first: uv tool install claude-listen")
    PROFILES.mkdir(parents=True, exist_ok=True)
    profile = {"Name": "Listen", "Guid": "claude-listen-pane", "Close Sessions On End": True, "Prompt Before Closing 2": 0}
    (PROFILES / "claude-listen.json").write_text(json.dumps({"Profiles": [profile]}, indent=2))
    COMMAND.parent.mkdir(parents=True, exist_ok=True)
    COMMAND.write_text(COMMAND_BODY)
    print("Done. Type /listen in Claude Code (restart open sessions to pick it up).")
