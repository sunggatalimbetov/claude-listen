"""Work out which Claude Code session the user means."""

import json
import os
import shlex
import sys
import subprocess
from pathlib import Path

SESSIONS = Path.home() / ".claude" / "sessions"


def _running() -> list[dict]:
    out = []
    for f in SESSIONS.glob("*.json"):
        try:
            info = json.loads(f.read_text())
            tty = subprocess.run(["ps", "-o", "tty=", "-p", str(info["pid"])], capture_output=True, text=True).stdout.strip()
        except (OSError, ValueError, KeyError):
            continue
        if tty and tty != "??":
            info["tty"] = "/dev/" + tty
            out.append(info)
    return out


def _iterm_tab_ttys() -> list[str]:
    script = 'tell application "iTerm2" to get tty of every session of current tab of current window'
    try:
        res = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [t.strip() for t in res.stdout.split(",") if t.strip()]


def current_session() -> str | None:
    """Session ID for: this Claude process (when run via `! listen`), else the Claude pane in the current iTerm tab."""
    if sid := os.environ.get("CLAUDE_CODE_SESSION_ID"):
        return sid
    if os.environ.get("TERM_PROGRAM") != "iTerm.app" and not os.environ.get("ITERM_SESSION_ID"):
        return None
    ttys = set(_iterm_tab_ttys())
    matches = [s for s in _running() if s["tty"] in ttys]
    if not matches:
        return None
    return max(matches, key=lambda s: s.get("updatedAt", 0))["sessionId"]


def open_pane(text: str) -> bool:
    """Open an iTerm split pane under the current one that reads `text`.

    The text is snapshotted now, so the reply Claude writes after `/listen` is not mixed in.
    """
    import tempfile

    fd, path = tempfile.mkstemp(prefix="listen-", suffix=".md")
    with os.fdopen(fd, "w") as f:
        f.write(text)
    from .install import ensure_profile

    ensure_profile()
    # Use this very executable, so it also works when run through uvx.
    exe = os.path.abspath(sys.argv[0]) if os.path.isfile(sys.argv[0]) else "listen"
    cmd = f"{shlex.quote(exe)} --pane --snapshot {shlex.quote(path)}"
    applescript_cmd = cmd.replace("\\", "\\\\").replace('"', '\\"')
    for profile in ('profile "Listen"', "default profile"):
        script = f'tell application "iTerm2" to tell current session of current window to split horizontally with {profile} command "{applescript_cmd}"'
        if subprocess.run(["osascript", "-e", script], capture_output=True, text=True).returncode == 0:
            return True
    os.unlink(path)
    return False
