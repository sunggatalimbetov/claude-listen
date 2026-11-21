"""Turn markdown into speakable chunks. Display text and spoken text are the same string,
so ElevenLabs character timings map straight onto what is on screen."""

import re
from dataclasses import dataclass

MAX_CHUNK = 500


@dataclass
class Chunk:
    text: str
    prefix: str = ""
    code: bool = False
    gap_before: bool = False


_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
_URL = re.compile(r"https?://([^/\s)]+)[^\s)]*")
_EMPH = re.compile(r"(\*\*|__|\*|`)")
_SYMBOLS = re.compile(r"[\U0001F000-\U0001FFFF☀-➿️‍]")
_BULLET = re.compile(r"^\s*(?:[-*+•]|\d+[.)])\s+")
_SENT = re.compile(r"(?<=[.!?…])\s+")


def clean_inline(s: str) -> str:
    s = _LINK.sub(r"\1", s)
    s = _URL.sub(lambda m: m.group(1).removeprefix("www."), s)
    s = _EMPH.sub("", s)
    s = _SYMBOLS.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHUNK:
        return [text]
    out, cur = [], ""
    for sent in _SENT.split(text):
        if cur and len(cur) + len(sent) + 1 > MAX_CHUNK:
            out.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


def parse(md: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    para: list[str] = []
    gap = False

    def flush():
        nonlocal para, gap
        text = clean_inline(" ".join(para))
        para = []
        if text:
            for i, piece in enumerate(_split_long(text)):
                chunks.append(Chunk(piece, gap_before=gap and i == 0))
            gap = False

    lines = md.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("```"):
            flush()
            body = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            if body:
                chunks.append(Chunk("\n".join(body), code=True, gap_before=True))
            gap = True
        elif not stripped or re.fullmatch(r"[-*_]{3,}", stripped):
            flush()
            gap = True
        elif stripped.startswith("|"):
            flush()
            if not re.fullmatch(r"[|:\-\s]+", stripped):
                cells = [clean_inline(c) for c in stripped.strip("|").split("|")]
                text = ", ".join(c for c in cells if c)
                if text:
                    chunks.append(Chunk(text + ".", prefix="• ", gap_before=gap))
                    gap = False
        elif _BULLET.match(line):
            flush()
            text = clean_inline(_BULLET.sub("", line))
            indent = "  " * min((len(line) - len(line.lstrip())) // 2, 3)
            for j, piece in enumerate(_split_long(text)):
                chunks.append(Chunk(piece, prefix=(indent + "• ") if j == 0 else indent + "  ", gap_before=gap and j == 0))
            gap = False
        else:
            if stripped.startswith("#"):
                flush()
                para.append(stripped.lstrip("#").strip())
                flush()
            else:
                para.append(stripped)
        i += 1
    flush()
    return chunks
