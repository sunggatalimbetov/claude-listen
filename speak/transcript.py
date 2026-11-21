"""Find the latest Claude Code reply in ~/.claude/projects transcripts."""

import json
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"


def transcript_path(session_id: str | None = None) -> Path | None:
    pattern = f"*/{session_id}.jsonl" if session_id else "*/*.jsonl"
    files = [p for p in PROJECTS.glob(pattern) if p.is_file()]
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


def last_reply(session_id: str | None = None) -> str:
    path = transcript_path(session_id)
    if path is None:
        return ""
    entries = []
    for line in path.read_text(errors="replace").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    groups: list[list[str]] = [[]]
    for e in entries:
        if _is_real_prompt(e):
            groups.append([])
            continue
        if e.get("type") != "assistant" or e.get("isSidechain"):
            continue
        content = (e.get("message") or {}).get("content")
        if isinstance(content, list):
            groups[-1] += [b["text"] for b in content if b.get("type") == "text" and b.get("text", "").strip()]
    # The newest reply, or the one before it if Claude is still writing.
    for parts in reversed(groups):
        if parts:
            return "\n\n".join(parts)
    return ""
