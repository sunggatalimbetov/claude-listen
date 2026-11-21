"""Plays PCM through afplay. Seek, pause and speed work by restarting afplay from a sample offset."""

import os
import subprocess
import tempfile
import time
import wave

from .tts import RATE, Audio


class Player:
    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.audio: Audio | None = None
        self.offset = 0.0
        self.started = 0.0
        self.rate = 1.0
        self.paused = False
        self._tmp = tempfile.mkdtemp(prefix="speak-")

    def position(self) -> float:
        if self.audio is None:
            return 0.0
        if self.paused or self.proc is None:
            return self.offset
        return min(self.offset + (time.monotonic() - self.started) * self.rate, self.audio.duration)

    def done(self) -> bool:
        return self.audio is not None and not self.paused and self.position() >= self.audio.duration

    def play(self, audio: Audio, at: float = 0.0):
        self.stop()
        self.audio, self.offset, self.paused = audio, at, False
        start = int(at * RATE) * 2
        path = os.path.join(self._tmp, f"{time.monotonic_ns()}.wav")
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(audio.pcm[start:])
        self.proc = subprocess.Popen(
            ["afplay", "-r", f"{self.rate:.2f}", "-q", "1", path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.started = time.monotonic()

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait()
        self.proc = None

    def toggle_pause(self):
        if self.audio is None:
            return
        if self.paused:
            self.play(self.audio, self.offset)
        else:
            self.offset = self.position()
            self.stop()
            self.paused = True

    def set_rate(self, rate: float):
        pos = self.position()
        self.rate = max(0.5, min(2.5, round(rate, 2)))
        if self.audio and not self.paused:
            self.play(self.audio, pos)
