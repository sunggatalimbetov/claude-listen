# claude-listen

Listen to your latest Claude Code reply instead of reading it. Each word is highlighted in the terminal as it is spoken.

- Reads the last reply from your most recent Claude Code session (`~/.claude/projects`)
- ElevenLabs voices (default model `eleven_v4`), with per-character timestamps for exact highlighting
- Generates paragraph by paragraph, so audio starts in about a second
- Code blocks are shown, not read: playback pauses 5 seconds so you can look at them
- Optional free, offline voice with Kokoro (`--local`)
- macOS (uses `afplay`)

## Install

```
uv tool install git+https://github.com/<you>/claude-listen
```

Add your ElevenLabs API key (Text to Speech access is enough, plus Voices read for `--voices`):

```
mkdir -p ~/.config/speak
echo "ELEVENLABS_API_KEY=sk_..." > ~/.config/speak/env
chmod 600 ~/.config/speak/env
```

Or export `ELEVENLABS_API_KEY`.

## Use

```
listen                 # read the latest Claude reply
listen notes.md        # read a file
pbpaste | listen       # read the clipboard
listen --voices        # list voices
listen --set-voice George
listen --local         # Kokoro, offline
```

Keys: `space` pause, `←/→` previous/next paragraph, `+/-` speed, `q` quit.

### iTerm hotkey

Enable iTerm's Python API (Settings > General > Magic), then run:

```
uv run scripts/install_iterm.py
```

Cmd+Shift+L then opens a pane below the current one that reads the latest reply and closes when it finishes.

If you run several Claude sessions at once, `listen` reads the one that replied most recently.

### Local voice (Kokoro)

```
uv tool install "claude-listen[local] @ git+https://github.com/<you>/claude-listen"
```

Put `kokoro-v1.0.onnx` and `voices-v1.0.bin` from the [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases) in `~/.cache/speak/kokoro/`. Highlighting with Kokoro is estimated, not exact.

## Config

| Env var | Default |
| --- | --- |
| `ELEVENLABS_API_KEY` | read from `~/.config/speak/env` |
| `SPEAK_MODEL` | `eleven_v4` |
| `SPEAK_CONFIG` | `~/.config/speak/config.json` |

Audio is cached in `~/.cache/speak`, so replaying a reply costs no credits.

## License

MIT
