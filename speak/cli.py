"""listen: read the latest Claude Code reply aloud, highlighting each word as it is spoken."""

import argparse
import bisect
import json
import os
import select
import stat
import sys
import termios
import time
import tty
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from . import tts
from .player import Player
from .segments import Chunk, parse
from .sessions import current_session, open_pane
from .transcript import last_reply

CONFIG = Path(os.environ.get("SPEAK_CONFIG", Path.home() / ".config" / "speak" / "config.json"))
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # George, a premade ElevenLabs voice
CODE_PAUSE = 5.0
PARA_GAP = 0.35
PREFETCH = 3

HELP = "space pause · ←/→ prev/next · +/- speed · q quit"


def load_config() -> dict:
    try:
        return json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        return {}


def save_config(cfg: dict):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n")


def list_voices() -> list[dict]:
    req = urllib.request.Request("https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": tts._api_key()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["voices"]


def resolve_voice(name: str) -> str:
    if len(name) == 20 and name.isalnum():
        return name
    for v in list_voices():
        if v["name"].lower().startswith(name.lower()):
            return v["voice_id"]
    sys.exit(f"No voice matching {name!r}. Run: listen --voices")


class Session:
    def __init__(self, chunks: list[Chunk], synth):
        self.chunks = chunks
        self.synth = synth
        self.pool = ThreadPoolExecutor(max_workers=2)
        self.futures: dict[int, Future] = {}
        self.player = Player()
        self.cur = 0
        self.wait_until = 0.0
        self.code_left = CODE_PAUSE
        self.started_chunk = False
        self.error = ""

    def _context(self, i: int, step: int) -> str:
        j = i + step
        while 0 <= j < len(self.chunks) and self.chunks[j].code:
            j += step
        return self.chunks[j].text if 0 <= j < len(self.chunks) else ""

    def prefetch(self):
        for i in range(self.cur, min(self.cur + PREFETCH + 1, len(self.chunks))):
            if i not in self.futures and not self.chunks[i].code:
                self.futures[i] = self.pool.submit(self.synth, self.chunks[i].text, prev=self._context(i, -1), nxt=self._context(i, 1))

    def go(self, i: int):
        self.player.stop()
        self.player.audio = None
        self.cur = max(0, min(i, len(self.chunks)))
        self.started_chunk = False
        self.code_left = CODE_PAUSE
        self.wait_until = 0.0

    def tick(self) -> bool:
        """Advance playback. Returns False when everything has been read."""
        if self.cur >= len(self.chunks):
            return False
        self.prefetch()
        chunk = self.chunks[self.cur]
        now = time.monotonic()
        if self.player.paused:
            return True
        if chunk.code:
            if not self.started_chunk:
                self.started_chunk, self.code_tick = True, now
            self.code_left -= now - self.code_tick
            self.code_tick = now
            if self.code_left <= 0:
                self.go(self.cur + 1)
            return True
        if not self.started_chunk:
            if now < self.wait_until:
                return True
            fut = self.futures[self.cur]
            if not fut.done():
                return True
            try:
                audio = fut.result()
            except Exception as e:  # noqa: BLE001 - shown on screen, then skip the chunk
                self.error = str(e)
                self.futures.pop(self.cur)
                self.go(self.cur + 1)
                return True
            self.player.play(audio)
            self.started_chunk = True
        elif self.player.done():
            nxt = self.cur + 1
            self.go(nxt)
            if nxt < len(self.chunks) and self.chunks[nxt].gap_before:
                self.wait_until = time.monotonic() + PARA_GAP
        return True

    def toggle_pause(self):
        chunk = self.chunks[self.cur] if self.cur < len(self.chunks) else None
        if chunk and (chunk.code or not self.started_chunk):
            self.player.paused = not self.player.paused
            self.code_tick = time.monotonic()
        else:
            self.player.toggle_pause()

    def loading(self) -> bool:
        if self.cur >= len(self.chunks) or self.chunks[self.cur].code or self.started_chunk:
            return False
        fut = self.futures.get(self.cur)
        return fut is None or not fut.done()

    def render(self, height: int) -> Group:
        p = self.player
        state = "⏸ paused" if p.paused else ("… generating" if self.loading() else "▶ playing")
        status = Text.assemble(
            (f" {state} ", "bold"),
            (f" {min(self.cur + 1, len(self.chunks))}/{len(self.chunks)} ", "cyan"),
            (f" {p.rate:.1f}x ", "magenta"),
            (f"  {HELP}", "grey50"),
        )
        rows: list = [status]
        if self.error:
            rows.append(Text(f" {self.error}", "red"))
        rows.append(Text(""))
        lines_left = height - len(rows) - 1
        start = max(0, self.cur - 2)
        for i in range(start, len(self.chunks)):
            if lines_left <= 0:
                break
            item = self._render_chunk(i)
            if self.chunks[i].gap_before and i != start:
                rows.append(Text(""))
                lines_left -= 1
            rows.append(item)
            lines_left -= self.chunks[i].text.count("\n") + 2 + len(self.chunks[i].text) // 80
        return Group(*rows)

    def _render_chunk(self, i: int):
        c = self.chunks[i]
        current = i == self.cur
        if c.code:
            title = f"code · continuing in {max(self.code_left, 0):.0f}s" if current else "code"
            return Panel(Text(c.text, "white" if current else "grey50"), title=title, border_style="yellow" if current else "grey35", expand=False)
        if i < self.cur:
            return Text(c.prefix + c.text, "grey50")
        if not current:
            return Text(c.prefix + c.text, "grey70")
        t = Text(c.prefix, "bold white")
        audio = self.player.audio
        if not self.started_chunk or audio is None:
            t.append(c.text, "bold white")
            return t
        k = bisect.bisect_right(audio.starts, self.player.position()) - 1
        k = max(0, min(k, len(c.text) - 1))
        a = k
        while a > 0 and not c.text[a - 1].isspace():
            a -= 1
        b = k
        while b < len(c.text) and not c.text[b].isspace():
            b += 1
        t.append(c.text[:a], "white")
        t.append(c.text[a:b], "bold black on yellow")
        t.append(c.text[b:], "bold white")
        return t


def read_key(timeout: float) -> str:
    r, _, _ = select.select([sys.stdin], [], [], timeout)
    if not r:
        return ""
    ch = os.read(sys.stdin.fileno(), 1).decode(errors="ignore")
    if ch == "\x1b":
        r, _, _ = select.select([sys.stdin], [], [], 0.01)
        if r:
            ch += os.read(sys.stdin.fileno(), 8).decode(errors="ignore")
    return ch


def run(chunks: list[Chunk], synth):
    s = Session(chunks, synth)
    console = Console()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    end_at = None
    try:
        tty.setcbreak(fd)
        with Live(s.render(console.height), console=console, screen=True, auto_refresh=False) as live:
            while True:
                key = read_key(1 / 30)
                if key in ("q", "Q", "\x1b"):
                    break
                if key == " ":
                    s.toggle_pause()
                elif key in ("\x1b[C", "l", "n"):
                    s.go(s.cur + 1)
                elif key in ("\x1b[D", "h", "p"):
                    s.go(s.cur - 1 if not s.started_chunk or s.player.position() < 1.5 else s.cur)
                elif key in ("+", "="):
                    s.player.set_rate(s.player.rate + 0.1)
                elif key in ("-", "_"):
                    s.player.set_rate(s.player.rate - 0.1)
                if not s.tick():
                    end_at = end_at or time.monotonic()
                    if time.monotonic() - end_at > 1.0:
                        break
                live.update(s.render(console.height), refresh=True)
    finally:
        s.player.stop()
        s.pool.shutdown(wait=False, cancel_futures=True)
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main():
    try:
        _main()
    except SystemExit as e:
        if "--pane" in sys.argv and e.code not in (0, None):
            if isinstance(e.code, str):
                print(e.code)
            input("\nPress Enter to close.")
        raise
    except Exception as e:
        if "--pane" not in sys.argv:
            raise
        print(f"listen failed: {e}")
        input("\nPress Enter to close.")


def _main():
    ap = argparse.ArgumentParser(prog="listen", description="Read the latest Claude Code reply aloud with word highlighting.")
    ap.add_argument("file", nargs="?", help="read this file instead ('-' for stdin)")
    ap.add_argument("--voice", help="ElevenLabs voice name or id for this run")
    ap.add_argument("--set-voice", metavar="NAME", help="save a default voice")
    ap.add_argument("--voices", action="store_true", help="list your ElevenLabs voices")
    ap.add_argument("--local", action="store_true", help="use local Kokoro instead of ElevenLabs")
    ap.add_argument("--session", help="Claude Code session id to read (default: the current one)")
    ap.add_argument("--pane", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--snapshot", help=argparse.SUPPRESS)
    ap.add_argument("--print", action="store_true", help="print the text that would be read, then exit")
    args = ap.parse_args()

    cfg = load_config()
    if args.voices:
        for v in list_voices():
            mark = "*" if v["voice_id"] == cfg.get("voice", DEFAULT_VOICE) else " "
            print(f"{mark} {v['name']}  ({v['voice_id']})")
        return
    if args.set_voice:
        cfg["voice"] = resolve_voice(args.set_voice)
        save_config(cfg)
        print(f"Default voice set to {cfg['voice']}")
        return

    mode = os.fstat(sys.stdin.fileno()).st_mode
    piped = (stat.S_ISFIFO(mode) or stat.S_ISREG(mode)) and not os.environ.get("CLAUDE_CODE_SESSION_ID")
    if args.file == "-" or (args.file is None and not args.snapshot and piped):
        md = sys.stdin.read()
        sys.stdin = open("/dev/tty")
    elif args.snapshot:
        md = Path(args.snapshot).read_text()
        Path(args.snapshot).unlink(missing_ok=True)
    elif args.file:
        md = Path(args.file).read_text()
    else:
        session = args.session or current_session()
        if not args.print and not sys.stdout.isatty() and os.environ.get("CLAUDE_CODE_SESSION_ID"):
            # Run from inside Claude Code (`! listen`): there is no screen here, so open a pane.
            if open_pane(last_reply(session)):
                print("Listening in a pane below.")
                return
            sys.exit("Could not open an iTerm pane. Run `listen` in a terminal instead.")
        md = last_reply(session)
    chunks = parse(md)
    if not chunks:
        sys.exit("Nothing to read: no Claude reply found.")
    if args.print:
        for c in chunks:
            print(("[code]\n" + c.text) if c.code else c.prefix + c.text)
        return

    if args.local:
        synth = lambda text, **_: tts.kokoro(text)  # noqa: E731
    else:
        voice = resolve_voice(args.voice) if args.voice else cfg.get("voice", DEFAULT_VOICE)
        synth = lambda text, prev="", nxt="": tts.eleven(text, voice, prev, nxt)  # noqa: E731
    run(chunks, synth)


if __name__ == "__main__":
    main()
