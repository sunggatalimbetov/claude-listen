# /// script
# requires-python = ">=3.11"
# dependencies = ["iterm2"]
# ///
"""Add an iTerm2 hotkey (Cmd+Shift+L) that opens a split pane running `listen`.

Run with: uv run scripts/install_iterm.py
Needs iTerm2's Python API enabled (Settings > General > Magic > Enable Python API).
"""

import json
import shutil
import sys
from pathlib import Path

import iterm2
from iterm2.binding import (
    BindingAction,
    KeyBinding,
    async_get_global_key_bindings,
    async_set_global_key_bindings,
)
from iterm2.keyboard import Keycode, Modifier

GUID = "claude-listen-pane"
PROFILES = Path.home() / "Library" / "Application Support" / "iTerm2" / "DynamicProfiles"


def write_profile():
    exe = shutil.which("listen")
    if not exe:
        sys.exit("`listen` is not on PATH. Install it first: uv tool install claude-listen")
    PROFILES.mkdir(parents=True, exist_ok=True)
    profile = {
        "Name": "Listen",
        "Guid": GUID,
        "Custom Command": "Yes",
        "Command": exe,
        "Close Sessions On End": True,
        "Prompt Before Closing 2": 0,
    }
    (PROFILES / "claude-listen.json").write_text(json.dumps({"Profiles": [profile]}, indent=2))


async def main(connection):
    write_profile()
    try:
        existing = await async_get_global_key_bindings(connection)
    except TypeError:  # no global bindings yet
        existing = []
    bindings = [b for b in existing if b.action != BindingAction.SPLIT_HORIZONTALLY_WITH_PROFILE or b.param != GUID]
    bindings.append(
        KeyBinding(ord("l"), [Modifier.COMMAND, Modifier.SHIFT], Keycode.ANSI_L, BindingAction.SPLIT_HORIZONTALLY_WITH_PROFILE, GUID, None, None)
    )
    await async_set_global_key_bindings(connection, bindings)
    print("Done. Press Cmd+Shift+L in iTerm to listen to the latest Claude reply.")


iterm2.run_until_complete(main)
