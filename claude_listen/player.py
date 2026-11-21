"""Plays PCM through macOS AVAudioPlayer, which reports the exact playback position,
pauses instantly and changes speed without changing pitch."""

import io
import wave

from AVFoundation import AVAudioPlayer
from Foundation import NSData

from .tts import RATE, Audio


def _wav_bytes(pcm: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return buf.getvalue()


class Player:
    def __init__(self):
        self.audio: Audio | None = None
        self._player = None
        self.rate = 1.0
        self.paused = False

    def position(self) -> float:
        return float(self._player.currentTime()) if self._player is not None else 0.0

    def done(self) -> bool:
        return self._player is not None and not self.paused and not self._player.isPlaying()

    def play(self, audio: Audio, at: float = 0.0):
        self.stop()
        data = _wav_bytes(audio.pcm)
        player, err = AVAudioPlayer.alloc().initWithData_error_(NSData.dataWithBytes_length_(data, len(data)), None)
        if player is None:
            raise RuntimeError(f"Could not play audio: {err}")
        player.setEnableRate_(True)
        player.setRate_(self.rate)
        player.setCurrentTime_(at)
        player.prepareToPlay()
        player.play()
        self.audio, self._player, self.paused = audio, player, False

    def stop(self):
        if self._player is not None:
            self._player.stop()
        self._player = None
        self.audio = None
        self.paused = False

    def close(self):
        self.stop()

    def toggle_pause(self):
        if self._player is None:
            return
        if self.paused:
            self._player.play()
        else:
            self._player.pause()
        self.paused = not self.paused

    def set_rate(self, rate: float):
        self.rate = max(0.5, min(2.0, round(rate, 2)))
        if self._player is not None:
            self._player.setRate_(self.rate)
