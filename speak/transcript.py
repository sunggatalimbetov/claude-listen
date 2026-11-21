"""Find the latest Claude Code reply in ~/.claude/projects transcripts."""

import json
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"


def _latest_transcript() -> Path | None:
    files = [p for p in PROJECTS.glob("*/*.jsonl") if p.is_file()]
    return max(files, key=lambda p: p.stat().st_mtime, default=None)


def _is_real_prompt(entry: dict) -> bool:
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return not content.lstrip().startswith("<")
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content if b.get("type") == "text"]
        return bool(texts) and not texts[0].lstrip().startswith("<")
    return False


def last_reply() -> str:
    path = _latest_transcript()
    if path is None:
        return ""
    entries = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    start = 0
    for i, e in enumerate(entries):
        if _is_real_prompt(e):
            start = i + 1
    parts = []
    for e in entries[start:]:
        if e.get("type") != "assistant" or e.get("isSidechain"):
            continue
        content = (e.get("message") or {}).get("content")
        if isinstance(content, list):
            parts += [b["text"] for b in content if b.get("type") == "text" and b.get("text", "").strip()]
    return "\n\n".join(parts)
