# claude-listen

Listen to your latest Claude Code reply instead of reading it. Each word is highlighted in the terminal as it is spoken.

- Reads the last reply of the Claude Code session you are in, even with many sessions open
- ElevenLabs voices (default model `eleven_v4`), with per-character timestamps for exact highlighting
- Generates paragraph by paragraph, so audio starts in about a second
- Code blocks are shown, not read: playback pauses 5 seconds so you can look at them
- Optional free, offline voice with Kokoro (`--local`)
- macOS (uses `afplay`)

## Install

### As a Claude Code plugin (easiest)

Needs [uv](https://docs.astral.sh/uv/) and iTerm2.

```
/plugin marketplace add sunggatalimbetov/claude-listen
/plugin install listen-aloud@listen-aloud
```

Then type `/listen` in any session.

### As a CLI

```
uv tool install claude-listen      # or: pipx install claude-listen
listen --install                   # adds /listen to Claude Code
```

### API key

Create an ElevenLabs key with Text to Speech access (plus Voices read for `--voices`):

```
mkdir -p ~/.config/speak
echo "ELEVENLABS_API_KEY=sk_..." > ~/.config/speak/env
chmod 600 ~/.config/speak/env
```

Or export `ELEVENLABS_API_KEY`.

## Use

```
listen                 # read the latest reply (Claude pane in this iTerm tab)
! listen               # typed inside Claude Code: opens a pane reading this session
listen notes.md        # read a file
pbpaste | listen       # read the clipboard
listen --voices        # list voices
listen --set-voice George
listen --local         # Kokoro, offline
```

Keys: `space` pause, `←/→` previous/next paragraph, `+/-` speed, `q` quit.

### `/listen` in Claude Code (iTerm2)

Type `/listen` in any Claude Code session. A pane opens below, reads that session's last reply and closes when it finishes. `! listen` does the same without a model turn.

### Which session is read

1. `--session <id>` if given
2. Inside Claude Code (`/listen` or `! listen`): that session, via `CLAUDE_CODE_SESSION_ID`
3. In iTerm: the Claude pane in the current tab (matched by tty through `~/.claude/sessions`)
4. Otherwise: the session that replied most recently

### Local voice (Kokoro)

```
uv tool install "claude-listen[local]"
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
