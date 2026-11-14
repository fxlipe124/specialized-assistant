# Telegram Channel Integration

You have a Telegram bot connected via an MCP server. Messages from Telegram arrive as `<channel source="telegram" chat_id="..." message_id="..." user="...">` tags. Reply using the MCP tools described below.

---

## MCP Tools

| Tool | Purpose |
|---|---|
| `mcp__plugin_telegram_telegram__reply` | Send text + optional file attachments. Params: `chat_id`, `text`, `reply_to` (message_id), `files` (array of absolute paths). Auto-chunks at 4096 chars. Images (`.jpg`/`.png`/`.gif`/`.webp`) send as photos; other types as documents. Max 50MB each. |
| `mcp__plugin_telegram_telegram__react` | Add emoji reaction. Only Telegram's fixed whitelist: 👍 👎 ❤ 🔥 🥰 👏 😁 🤔 🤯 😱 🤬 😢 🎉 🤩 🤮 💩 🙏 👌 🕊 🤡 🥱 🥴 😍 🐳 ❤‍🔥 🌚 🌭 💯 🤣 ⚡ 🍌 🏆 💔 🤨 😐 🍓 🍾 💋 🖕 😈 😴 😭 🤓 👻 👨‍💻 👀 🎃 🙈 😇 😨 🤝 ✍ 🤗 🫡 🎅 🎄 ☃ 💅 🤪 🗿 🆒 💘 🙉 🦄 😘 💊 🙊 😎 👾 🤷‍♂ 🤷 🤷‍♀ 😡 |
| `mcp__plugin_telegram_telegram__edit_message` | Edit a previously sent bot message. No push notification triggered. |
| `mcp__plugin_telegram_telegram__download_attachment` | Download file by `attachment_file_id` to `~/.claude/channels/telegram/inbox/`. |

---

## Reply Behavior

- **Threading:** Always pass `reply_to` with the `message_id` of the message being answered, so the user can match responses to questions.
- **Processing indicator:** Immediately react with 👨‍💻 on message receipt to show processing. When the response is ready: (1) remove the reaction, (2) send typing indicator, (3) reply.
- **Removing reactions / typing indicator:** The MCP plugin has no tools for these. Use the Telegram API directly via curl:
  ```bash
  source ~/.claude/channels/telegram/.env
  # Remove reaction
  curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setMessageReaction" \
    -H "Content-Type: application/json" \
    -d '{"chat_id": <chat_id>, "message_id": <msg_id>, "reaction": []}'
  # Send typing indicator
  curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendChatAction" \
    -H "Content-Type: application/json" \
    -d '{"chat_id": <chat_id>, "action": "typing"}'
  ```
- **Long tasks:** If processing will take a while (heavy I/O, multiple MCP calls), send a brief text like "Thinking, one moment" before starting. Don't do this for quick replies.
- **No message editing as feedback:** Edits don't trigger push notifications. Always send a new message instead.
- **File delivery:** Small `.md` content goes inline in the message. Large `.md` goes as a file attachment -- the user can open `.md` files fine.

---

## Handling Inbound Attachments

### Photos (`attachment_kind="photo"` or `image_path` attribute)

1. If the message has `image_path`: Read that file directly (Claude sees it natively)
2. If it has `attachment_file_id`: download with `download_attachment`, then Read the downloaded file
3. Respond naturally about what you see, in the context of the conversation

### Voice messages (`attachment_kind="voice"`)

1. Download: `mcp__plugin_telegram_telegram__download_attachment` with the `attachment_file_id`
2. Transcribe: `~/.claude/scripts/transcribe-telegram-voice.sh <downloaded_file_path>`
3. Use the transcribed text as the user's message -- process it as if they had typed it
4. Do NOT quote the transcription back unless ambiguous

### Video notes (`attachment_kind="video_note"`)

Round videos recorded in Telegram. Handle both audio and visual:

1. Download the attachment
2. Extract audio: `TMP=$(mktemp /tmp/vnote_XXXXXX.oga) && ffmpeg -i <downloaded.mp4> -vn -ar 16000 -ac 1 -y "$TMP" 2>/dev/null`
3. Transcribe: `~/.claude/scripts/transcribe-telegram-voice.sh "$TMP"` then `rm "$TMP"`
4. Extract 3-4 visual frames: `~/.claude/scripts/extract-media-frames.sh <file> 4`
5. Read each frame
6. Combine audio transcription + visual description
7. Clean up: `rm -rf <FRAME_DIR>`

### GIFs / Animations (`attachment_kind="animation"`)

1. Download the attachment
2. Extract 4 sample frames: `~/.claude/scripts/extract-media-frames.sh <file> 4`
3. Read each extracted frame PNG
4. Describe the GIF as a whole
5. Clean up: `rm -rf <FRAME_DIR>`

### Videos (`attachment_kind="video"`)

1. Download the attachment
2. Extract up to 10 frames: `~/.claude/scripts/extract-media-frames.sh <file> 10`
3. Read each frame
4. Also extract and transcribe audio if present:
   ```bash
   TMP=$(mktemp /tmp/vid_XXXXXX.oga)
   ffmpeg -i <file> -vn -ar 16000 -ac 1 -y "$TMP" 2>/dev/null
   ~/.claude/scripts/transcribe-telegram-voice.sh "$TMP"
   rm -f "$TMP"
   ```
5. Describe combining visual + audio
6. Clean up: `rm -rf <FRAME_DIR>`

---

## Code Formatting

When sending code blocks or diffs via Telegram:

- **Short (< ~3500 chars total message):** Use `format: "markdownv2"`. Wrap code in fenced blocks with language hints. Escape `_ * [ ] ( ) ~ > # + - = | { } . !` outside code blocks.
- **Large (> ~3500 chars):** Write to a temp file with the correct extension (`.go`, `.py`, `.diff`, `.patch`, `.ts`, `.sh`, `.json`, `.sql`, `.md`, `.txt`) and attach via the `files` param.
- Telegram hard limit is 4096 chars per message.

---

## Reply Mode: Text vs Audio

Each chat has two persistent settings: **mode** (text/audio) and **voice** (provider:id:params or dynamic).

### Check mode before EVERY reply

```bash
~/.claude/scripts/telegram-reply-mode.sh get <chat_id>
# Returns "text" or "audio"
```

### Detect mode switch requests

- **To audio:** "respond in audio", "reply with voice", "fale por audio", "responda em audio", "manda audio"
- **To text:** "respond in text", "reply in text", "agora em texto", "responda em texto", "manda texto"

```bash
~/.claude/scripts/telegram-reply-mode.sh set <chat_id> audio   # or text
```

### Text mode

Just reply normally with the `reply` MCP tool.

### Audio mode

1. Compose your reply text
2. Get voice: `~/.claude/scripts/telegram-reply-mode.sh get-voice <chat_id>` -> `provider:voice_id:params` or `dynamic`
3. **If `dynamic`:** analyze the conversation topic and resolve the appropriate alias:

   | Topic | Alias to resolve |
   |---|---|
   | **Work** (code, bugs, tasks, PRs, meetings, technical) | resolve the "professional/serious" voice |
   | **Personal** (life, feelings, relationships, introspection) | resolve the user's own cloned voice |
   | **Everything else** (daily chat, jokes, general) | resolve the default casual voice |

   Use: `~/.claude/scripts/telegram-reply-mode.sh resolve "<alias>"`
   Do NOT persist the resolved voice -- keep `dynamic` in state.

4. Parse the resolved result:
   ```bash
   RESOLVED=$(~/.claude/scripts/telegram-reply-mode.sh resolve "<alias>")
   PROVIDER=$(echo "$RESOLVED" | cut -d: -f1)
   VOICE_ID=$(echo "$RESOLVED" | cut -d: -f2)
   PARAMS=$(echo "$RESOLVED" | sed 's/^[^{]*//')  # everything from first { onward
   ```

5. **If provider is `elevenlabs`:** check credits first:
   ```bash
   ~/.claude/scripts/elevenlabs-credits.sh --check
   ```
   - Exit 0: credits available, proceed
   - Exit 1: exhausted, fall back to OpenAI (`tts-openai.sh` with voice `nova` and `{"speed":1.1}`). Inform the user.

6. **If `model_id` in params is `eleven_v3`:** use audio tags `[like this]` in the text (see Audio Tags section below). If text exceeds 5,000 chars, switch to `eleven_multilingual_v2` and strip all tags.
   **If `eleven_multilingual_v2` or any other model:** NEVER use audio tags. The model reads them aloud as literal text.

7. Generate audio:
   - **OpenAI:** `~/.claude/scripts/tts-openai.sh "text" "" "voice" 'params_json'`
   - **ElevenLabs:** `~/.claude/scripts/tts-elevenlabs.sh "text" "" "voice_id" 'params_json'`

8. Send: `~/.claude/scripts/send-telegram-voice.sh <chat_id> /path/to/output.opus [reply_to]`
9. Clean up: `rm /path/to/output.opus`
10. **Text alongside audio:** By default, send ONLY the voice message. Only add a separate text message when the reply contains non-vocal content (code snippets, URLs, formatted data).

### Voice switch detection

When the user mentions a voice by alias (e.g. "use the professional voice", "fala com a nova"), resolve the alias and persist:

```bash
RESOLVED=$(~/.claude/scripts/telegram-reply-mode.sh resolve "<alias>")
# Parse PROVIDER, VOICE_ID, PARAMS from RESOLVED
~/.claude/scripts/telegram-reply-mode.sh set-voice <chat_id> <provider> <voice_id> '<params>'
```

To activate dynamic mode: "dynamic voice", "voz dinamica", "escolhe a voz", "voz automatica"
```bash
~/.claude/scripts/telegram-reply-mode.sh set-voice <chat_id> dynamic
```

---

## Audio Tags (ElevenLabs eleven_v3 only)

When composing text for a voice using `model_id: "eleven_v3"`, insert audio tags for natural, expressive speech.

### Syntax

- Format: `[tag text]` -- lowercase recommended
- Scope: tag persists until end of sentence or a contradicting tag
- Combinable: `[nervously][whispers]`
- Tags are always in English; spoken text can be in any language

### Text formatting (complements tags)

| Technique | Effect | Example |
|---|---|---|
| **UPPERCASE** word | Emphasis | "That is VERY important" |
| `...` | Hesitation | "I think... maybe not" |
| `--` (em dash) | Abrupt pause | "I was going to say -- oh, forget it" |
| Short sentences | Punchier delivery | "No. Absolutely not." |

### Context-aware tag density

| Context | Tag density | Favor |
|---|---|---|
| Casual daily chat | Medium | `[playfully]`, `[giggles]`, `[laughs]`, `[sarcastic]` |
| Intimate/partner | Medium | `[warmly]`, `[teasingly]`, `[laughs softly]`, `[gently]` |
| Work colleague | Low | `[conversational tone]`, `[matter-of-fact]`, `[calm]` |
| Professional/boss | Minimal | `[serious tone]`, `[deliberate]` |
| **Storytelling** | **High -- go all in** | **ALL categories freely** |
| Good news | Medium-high | `[excited]`, `[applause]`, `[cheerfully]` |
| Bad news | Low | `[calm]`, `[reflective]`, `[sighs]`, `[gently]` |
| Explaining | Low | `[matter-of-fact]`, `[deliberate]`, `[pause]` |

### Commonly used tags

**Emotions:** `[happy]`, `[sad]`, `[excited]`, `[calm]`, `[frustrated]`, `[nervous]`, `[sarcastic]`, `[playfully]`, `[warmly]`, `[gently]`, `[curious]`, `[thoughtful]`, `[cheerfully]`

**Delivery:** `[pause]`, `[short pause]`, `[long pause]`, `[rushed]`, `[slows down]`, `[deliberate]`, `[stammers]`, `[whispers]`, `[softly]`, `[loudly]`

**Reactions:** `[laughs]`, `[laughs softly]`, `[giggles]`, `[sighs]`, `[gasps]`, `[clears throat]`, `[exhales]`

**Narrator tones:** `[dramatic tone]`, `[matter-of-fact]`, `[conversational tone]`, `[sarcastic tone]`, `[reflective]`

**Sound effects:** `[applause]`, `[drumroll]`, `[footsteps]`, `[thunder]`, `[door slams]`

### Effective combos

| Combo | Use for |
|---|---|
| `[nervously][whispers]` | Anxious secret |
| `[excited][laughs]` | Joyful moment |
| `[sarcastic tone][deadpan]` | Dry humor |
| `[dramatic tone][pause]` | Building suspense |
| `[warmly][softly]` | Intimate/caring |
| `[calm][reassuring]` | Comforting |

### Anti-patterns

- Don't tag every sentence in casual conversation -- let some breathe naturally
- Don't use dramatic effects for mundane content
- Don't stack 4+ tags on one phrase
- Don't use `[laughs]` as filler
- No sound effects in professional context

---

## Voice Configuration Reference

Voices are defined in `~/.claude/channels/telegram/voices.conf`:

```
# Format: alias1, alias2, ... : provider : voice_id : {"json_params"...}
```

Each line maps one or more aliases to a provider, voice ID, and parameters. The `resolve` command looks up aliases case-insensitively.

### Available TTS providers

**ElevenLabs** (`tts-elevenlabs.sh`):
- Models: `eleven_v3` (supports audio tags), `eleven_multilingual_v2` (no tags, good for cloned voices)
- Params: `stability` (0-1), `similarity_boost` (0-1), `style` (0-1), `use_speaker_boost` (bool), `speed` (0.7-1.2), `model_id`
- Output: OGG Opus
- API key: `ELEVENLABS_API_KEY` from env or `~/.claude/channels/telegram/.env`

**OpenAI** (`tts-openai.sh`):
- Model: `tts-1`
- Voices: nova, alloy, echo, fable, onyx, shimmer
- Params: `speed` (0.25-4.0)
- Output: OGG Opus
- API key: `OPENAI_API_KEY` from env or `~/.claude.json`

---

## Helper Scripts Reference

All at `~/.claude/scripts/`:

| Script | Usage | Purpose |
|---|---|---|
| `telegram-reply-mode.sh` | `get\|set\|get-voice\|set-voice\|resolve <args>` | Mode/voice state management |
| `tts-openai.sh` | `"text" [output] [voice] [params_json]` | OpenAI TTS -> opus |
| `tts-elevenlabs.sh` | `"text" [output] [voice_id] [params_json]` | ElevenLabs TTS -> opus |
| `send-telegram-voice.sh` | `<chat_id> <file.opus> [reply_to]` | Send opus as Telegram voice msg |
| `transcribe-telegram-voice.sh` | `<input.oga>` | Whisper STT -> text on stdout |
| `extract-media-frames.sh` | `<input_file> [max_frames]` | GIF/video frame extraction |
| `elevenlabs-credits.sh` | `[--check]` | ElevenLabs credit check |

---

## Important Gotchas

- **Short TTS clips garble on Telegram.** Never generate audio for just 1-2 words. Always compose at least one full sentence.
- **Always persist voice selection.** After testing or switching voices, always call `set-voice` to save the state.
- **Never kill MCP processes manually.** Killing them removes tools permanently for the session. Fix config and retry instead.
- **No message history.** Telegram Bot API has no search or fetch. Bot only sees messages as they arrive. If you need earlier context, ask the user to paste or summarize.
- **Attachment size limits:** 20MB download (Telegram), 50MB send.

---

## Limitations

- Telegram message limit: 4096 characters (auto-chunked by the plugin)
- Emoji reactions: only the fixed whitelist above
- Single poller per token: the server kills stale pollers on startup
- Groups need explicit opt-in via access control
- Privacy mode in groups: if `requireMention: false`, privacy mode must be disabled via BotFather
