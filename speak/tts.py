"""Text to speech backends. Each returns 24 kHz mono int16 PCM plus a start time per character."""

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

RATE = 24000
CACHE = Path.home() / ".cache" / "speak"
KEY_FILE = Path(os.environ.get("SPEAK_ENV_FILE", Path.home() / ".config" / "speak" / "env"))
MODEL = os.environ.get("SPEAK_MODEL", "eleven_v4")


@dataclass
class Audio:
    pcm: bytes
    starts: list[float]

    @property
    def duration(self) -> float:
        return len(self.pcm) / 2 / RATE


def _api_key() -> str:
    if key := os.environ.get("ELEVENLABS_API_KEY"):
        return key
    if KEY_FILE.exists():
        for line in KEY_FILE.read_text().splitlines():
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise RuntimeError(f"Set ELEVENLABS_API_KEY or put it in {KEY_FILE}")


def _cached(kind: str, parts: list[str], make) -> Audio:
    digest = hashlib.sha256("\x00".join([kind, *parts]).encode()).hexdigest()[:32]
    pcm_path, meta_path = CACHE / f"{digest}.pcm", CACHE / f"{digest}.json"
    if pcm_path.exists() and meta_path.exists():
        return Audio(pcm_path.read_bytes(), json.loads(meta_path.read_text()))
    audio = make()
    CACHE.mkdir(parents=True, exist_ok=True)
    pcm_path.write_bytes(audio.pcm)
    meta_path.write_text(json.dumps(audio.starts))
    return audio


def _char_starts(text: str, chars: list[str], times: list[float], duration: float) -> list[float]:
    if "".join(chars) == text:
        return times
    if not chars:
        return [duration * i / max(len(text), 1) for i in range(len(text))]
    return [times[min(int(i * len(chars) / len(text)), len(chars) - 1)] for i in range(len(text))]


def eleven(text: str, voice: str, prev: str = "", nxt: str = "") -> Audio:
    def make() -> Audio:
        body = {"text": text, "model_id": MODEL}
        if prev:
            body["previous_text"] = prev
        if nxt:
            body["next_text"] = nxt
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=pcm_24000",
            data=json.dumps(body).encode(),
            headers={"xi-api-key": _api_key(), "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"ElevenLabs {e.code}: {e.read().decode(errors='replace')[:300]}") from None
        pcm = base64.b64decode(data["audio_base64"])
        al = data.get("alignment") or {}
        starts = _char_starts(text, al.get("characters") or [], al.get("character_start_times_seconds") or [], len(pcm) / 2 / RATE)
        return Audio(pcm, starts)

    return _cached("eleven", [MODEL, voice, text, prev, nxt], make)


KOKORO_DIR = CACHE / "kokoro"
_kokoro = None


def kokoro(text: str, voice: str = "af_heart", **_) -> Audio:
    def make() -> Audio:
        global _kokoro
        import numpy as np
        from kokoro_onnx import Kokoro

        if _kokoro is None:
            _kokoro = Kokoro(str(KOKORO_DIR / "kokoro-v1.0.onnx"), str(KOKORO_DIR / "voices-v1.0.bin"))
        samples, sr = _kokoro.create(text, voice=voice, lang="en-us")
        if sr != RATE:
            idx = np.linspace(0, len(samples) - 1, int(len(samples) * RATE / sr))
            samples = np.interp(idx, np.arange(len(samples)), samples)
        pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
        dur = len(pcm) / 2 / RATE
        return Audio(pcm, [dur * i / max(len(text), 1) for i in range(len(text))])

    return _cached("kokoro", [voice, text], make)
