# Telegram on Claude Code: Human Setup Guide

Step-by-step guide to connect a Telegram bot to Claude Code, with optional voice messages (TTS/STT) and media handling.

---

## 1. Prerequisites

| Dependency | Purpose | Install |
|---|---|---|
| **Bun** | MCP server runtime | `curl -fsSL https://bun.sh/install \| bash` |
| **ffmpeg + ffprobe** | Audio/video processing (voice, media frames) | `apt install ffmpeg` / `nix-env -iA nixpkgs.ffmpeg` |
| **python3** | JSON parsing in helper scripts | Usually pre-installed |
| **curl** | API calls | Usually pre-installed |
| **Claude Code** | The CLI | `npm install -g @anthropic-ai/claude-code` |

### API Keys

| Key | Required? | Purpose | Where to get |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Bot authentication | [@BotFather](https://t.me/BotFather) on Telegram |
| `OPENAI_API_KEY` | Optional | TTS (OpenAI voices) + Whisper transcription | [platform.openai.com](https://platform.openai.com) |
| `ELEVENLABS_API_KEY` | Optional | TTS (ElevenLabs voices) | [elevenlabs.io](https://elevenlabs.io) |

Voice features (audio replies, voice transcription) need the optional keys. Text-only works with just the bot token.

---

## 2. Create a Telegram Bot

1. Open [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`
3. Choose a **display name** (anything, spaces OK)
4. Choose a **username** ending in `bot` (e.g. `my_claude_bot`)
5. Copy the token: `123456789:AAHfiqksKZ8...` (the full string including the number and colon)

---

## 3. Install the Telegram Plugin

Start a Claude Code session and run these commands inside it:

```
/plugin install telegram@claude-plugins-official
/reload-plugins
```

This installs the plugin to `~/.claude/plugins/marketplaces/claude-plugins-official/external_plugins/telegram/`.

---

## 4. Enable Channels

Edit `~/.claude/settings.json` (or let Claude do it) to include:

```json
{
  "enabledPlugins": {
    "telegram@claude-plugins-official": true
  },
  "channelsEnabled": true
}
```

---

## 5. Configure the Bot Token

**Option A** -- use the built-in skill (inside a Claude Code session):
```
/telegram:configure 123456789:AAHfiqksKZ8...
```

**Option B** -- write the file by hand:
```bash
mkdir -p ~/.claude/channels/telegram
cat > ~/.claude/channels/telegram/.env <<'EOF'
TELEGRAM_BOT_TOKEN=<YOUR_BOT_TOKEN>
EOF
chmod 600 ~/.claude/channels/telegram/.env
```

If you plan to use ElevenLabs voices, add the key to the same file:
```bash
echo "ELEVENLABS_API_KEY=<YOUR_KEY>" >> ~/.claude/channels/telegram/.env
```

---

## 6. Launch Claude with Telegram

**This is the command you'll use every time:**

```bash
claude --channels plugin:telegram@claude-plugins-official
```

The `--channels` flag tells Claude Code to boot the Telegram MCP server alongside the session. Without it, the bot won't connect.

You can combine it with other flags as usual:
```bash
# With a specific working directory
claude --channels plugin:telegram@claude-plugins-official /path/to/project

# With auto mode
claude --channels plugin:telegram@claude-plugins-official --auto
```

---

## 7. Pair Your Telegram Account

With the Claude session running (from step 6):

1. Open Telegram and DM your bot -- it replies with a **6-character pairing code**
2. In your Claude Code session, type: `/telegram:access pair <code>`
3. Your Telegram user ID is added to the allowlist
4. Send another DM -- it now reaches Claude

### Lock down the bot

Once paired, switch policy so strangers can't get pairing codes:

```
/telegram:access policy allowlist
```

Now only allowlisted users can reach the bot. Unknown senders are silently dropped.

---

## 8. Access Control Reference

All state lives in `~/.claude/channels/telegram/access.json`. The `/telegram:access` skill manages it.

| Command | Effect |
|---|---|
| `/telegram:access` | Print current state |
| `/telegram:access pair <code>` | Approve pairing code |
| `/telegram:access deny <code>` | Discard pending code |
| `/telegram:access allow <user_id>` | Add user by numeric ID |
| `/telegram:access remove <user_id>` | Remove from allowlist |
| `/telegram:access policy <mode>` | `pairing`, `allowlist`, or `disabled` |
| `/telegram:access group add <group_id>` | Enable a group |
| `/telegram:access group rm <group_id>` | Disable a group |
| `/telegram:access set ackReaction <emoji>` | Set acknowledgment emoji |

**Getting user IDs:** Have the person message [@userinfobot](https://t.me/userinfobot) on Telegram.

**Groups:** Off by default. Supergroup IDs are negative (`-100...`). With the default `requireMention: true`, the bot only responds when @mentioned or replied to.

---

## 9. Teach Claude How to Use Telegram

The plugin gives Claude the basic tools (reply, react, edit, download). But for good behavior -- threading, voice messages, code formatting, media handling -- Claude needs instructions.

### Paste the Claude instructions

Copy the **entire contents** of `TELEGRAM-ON-CLAUDE-INSTRUCTIONS-FOR-CLAUDE.md` into your `~/.claude/CLAUDE.md` file (or into a project-level `CLAUDE.md`).

This teaches Claude:
- How to thread replies and show processing indicators
- How to handle voice messages, photos, GIFs, videos
- How to format code for Telegram's limits
- How to use text/audio reply modes with TTS
- The full audio pipeline (voice selection, credits check, TTS generation, sending)
- Audio tags for expressive speech (ElevenLabs eleven_v3)

Without these instructions, Claude will just use the basic `reply` tool and won't know about voice, media handling, or formatting rules.

---

## 10. Voice Setup (Optional)

Voice support lets Claude reply with native Telegram voice messages and transcribe incoming voice messages.

### 10.1 Helper scripts

Create `~/.claude/scripts/` and add these scripts (make them `chmod +x`):

| Script | Purpose |
|---|---|
| `telegram-reply-mode.sh` | Per-chat text/audio mode and voice state management |
| `tts-openai.sh` | OpenAI TTS -> OGG Opus |
| `tts-elevenlabs.sh` | ElevenLabs TTS -> OGG Opus |
| `send-telegram-voice.sh` | Send opus file as native Telegram voice message |
| `transcribe-telegram-voice.sh` | OpenAI Whisper STT (voice -> text) |
| `extract-media-frames.sh` | Extract frames from GIFs/videos for description |
| `elevenlabs-credits.sh` | Check ElevenLabs remaining credits |

These scripts read API keys from `~/.claude/channels/telegram/.env` (for `TELEGRAM_BOT_TOKEN` and `ELEVENLABS_API_KEY`) and from `~/.claude.json` (for `OPENAI_API_KEY`, under `mcpServers.openai-image.env.OPENAI_API_KEY`).

### 10.2 Voice registry

Create `~/.claude/channels/telegram/voices.conf`:

```
# alias1, alias2, ... : provider : voice_id : {"json_params"...}
#
# Example entries:
default voice, casual : elevenlabs : <VOICE_ID_A> : {"stability":0.5,"similarity_boost":0.75,"speed":1.1,"model_id":"eleven_v3"}
professional, serious : elevenlabs : <VOICE_ID_B> : {"stability":0.7,"similarity_boost":0.75,"speed":1.05,"model_id":"eleven_v3"}
my voice, clone       : elevenlabs : <VOICE_ID_C> : {"stability":0.7,"similarity_boost":1.0,"style":0.4,"speed":1.1,"model_id":"eleven_multilingual_v2"}
openai, nova, fallback: openai     : nova          : {"speed":1.1}
```

Voice IDs come from ElevenLabs (your voice library). The aliases are how you refer to voices in chat ("use the professional voice", "fala com a nova").

### 10.3 Skills

Skills are markdown instruction files that Claude loads automatically when trigger conditions match. Create them in `~/.claude/skills/<name>/SKILL.md`:

| Skill | Purpose |
|---|---|
| `telegram-reply-mode` | Checks text/audio mode before every reply, handles TTS pipeline |
| `telegram-voice-transcribe` | Transcribes voice messages and video notes via Whisper |
| `telegram-code-formatting` | Formats code/diffs for Telegram (inline vs file attachment) |
| `telegram-visual-media` | Describes photos, GIFs, videos using vision + frame extraction |
| `elevenlabs-v3-tags` | Audio tag reference for expressive eleven_v3 TTS |

The skill contents are detailed in `TELEGRAM-ON-CLAUDE-INSTRUCTIONS-FOR-CLAUDE.md`. You can create minimal versions or copy the full skill files from an existing setup.

### 10.4 Per-chat state

State is stored as plain text files in `~/.claude/channels/telegram/state/`:

```
~/.claude/channels/telegram/state/
  <chat_id>.mode    # "text" or "audio" (default: text)
  <chat_id>.voice   # "provider:voice_id:params" or "dynamic" (default: dynamic)
```

Users switch modes by saying things like "respond in audio" or "agora em texto" in the Telegram chat.

---

## 11. Architecture Overview

```
Telegram App
    |  (Bot API long-polling)
    v
MCP Server (server.ts, Bun + grammy)
    |  (MCP protocol, stdio)
    v
Claude Code Session (--channels flag)
    |
    |-- CLAUDE.md instructions (from FOR-CLAUDE file)
    |-- Skills (~/.claude/skills/)
    |-- Scripts (~/.claude/scripts/)
    |-- State (~/.claude/channels/telegram/state/)
    v
Replies via MCP tools + Telegram API (curl for voice/reactions)
```

### Message flow

1. User DMs bot on Telegram
2. MCP server receives via long-poll, checks access gate
3. Forwards to Claude as a `<channel>` notification
4. Claude processes (transcribes voice, reads images, etc.)
5. Claude composes reply, checks reply mode
6. Text mode: replies via MCP tool / Audio mode: generates TTS, sends voice message
7. If code in reply: formats for Telegram (inline or file attachment)

---

## 12. File Structure

```
~/.claude/
  settings.json                      # Plugin enablement, channelsEnabled: true
  CLAUDE.md                          # <-- paste FOR-CLAUDE instructions here

~/.claude/channels/telegram/
  .env                               # TELEGRAM_BOT_TOKEN, ELEVENLABS_API_KEY
  access.json                        # DM policy, allowlist, groups
  voices.conf                        # TTS voice aliases and parameters
  bot.pid                            # Running bot PID (managed by server)
  state/                             # Per-chat mode and voice settings
  approved/                          # Pairing approval signals (transient)
  inbox/                             # Downloaded attachments

~/.claude/scripts/                   # Helper scripts (chmod +x)
  telegram-reply-mode.sh
  tts-openai.sh
  tts-elevenlabs.sh
  send-telegram-voice.sh
  transcribe-telegram-voice.sh
  extract-media-frames.sh
  elevenlabs-credits.sh

~/.claude/skills/                    # Skill definitions (SKILL.md files)
  telegram-reply-mode/
  telegram-voice-transcribe/
  telegram-code-formatting/
  telegram-visual-media/
  elevenlabs-v3-tags/

~/.claude/plugins/.../telegram/      # Plugin source (installed by /plugin install)
  server.ts                          # MCP server (~1000 LOC)
  package.json                       # grammy + @modelcontextprotocol/sdk
  skills/                            # Built-in skills (access, configure)
```

---

## 13. Quick Start Checklist

### Minimum (text only)

1. [ ] Install Bun
2. [ ] Create bot via @BotFather, copy token
3. [ ] In Claude Code: `/plugin install telegram@claude-plugins-official` then `/reload-plugins`
4. [ ] `/telegram:configure <token>`
5. [ ] Set `channelsEnabled: true` in `~/.claude/settings.json`
6. [ ] Exit and relaunch: `claude --channels plugin:telegram@claude-plugins-official`
7. [ ] DM bot on Telegram, get pairing code
8. [ ] `/telegram:access pair <code>`
9. [ ] `/telegram:access policy allowlist`
10. [ ] Paste `TELEGRAM-ON-CLAUDE-INSTRUCTIONS-FOR-CLAUDE.md` into your `~/.claude/CLAUDE.md`

### Full (with voice + media)

11. [ ] Install ffmpeg
12. [ ] Add `ELEVENLABS_API_KEY` to `~/.claude/channels/telegram/.env`
13. [ ] Ensure `OPENAI_API_KEY` is available (for Whisper + TTS fallback)
14. [ ] Create helper scripts in `~/.claude/scripts/`, make them executable
15. [ ] Configure voices in `~/.claude/channels/telegram/voices.conf`
16. [ ] Create skills in `~/.claude/skills/`

---

## 14. Troubleshooting

**Bot doesn't respond to DMs:**
- Is Claude running with `--channels`? The flag is required.
- Is the policy `disabled`? Check with `/telegram:access`.
- Is your user ID in the allowlist? Check `access.json`.

**"Only one getUpdates consumer" errors:**
- Only one Claude session can poll the same bot token. The server kills stale pollers on startup, but if another process holds the connection, stop it first.

**Voice messages not working:**
- Is ffmpeg installed? (`which ffmpeg`)
- Is `OPENAI_API_KEY` available? (needed for Whisper transcription)
- Are scripts executable? (`chmod +x ~/.claude/scripts/*.sh`)

**ElevenLabs voices not generating:**
- Check credits: `~/.claude/scripts/elevenlabs-credits.sh`
- Is `ELEVENLABS_API_KEY` in `~/.claude/channels/telegram/.env`?

**MCP tools disappeared mid-session:**
- Never kill MCP processes manually. If tools vanish, start a new Claude session.

---

## 15. Limitations

- **No message history:** Telegram Bot API has no search or fetch. Bot only sees messages as they arrive.
- **Attachment size:** 20MB download limit (Telegram-imposed), 50MB send limit.
- **Message length:** 4096 characters per message (auto-chunked by the plugin).
- **Emoji reactions:** Only Telegram's fixed whitelist (~70 emoji).
- **Single poller:** One `getUpdates` consumer per bot token. Can't run two Claude sessions with the same bot.
- **Privacy mode:** Groups with `requireMention: false` need privacy mode disabled via BotFather (`/setprivacy` -> Disable).
