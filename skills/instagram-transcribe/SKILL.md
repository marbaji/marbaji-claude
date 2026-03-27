---
name: instagram-transcribe
description: Transcribe and summarize Instagram Reels (or any video URL supported by yt-dlp) using yt-dlp and Whisper. Use when the user shares an Instagram Reel URL and wants a transcript or summary.
---

# Instagram Reel Transcriber

Transcribes audio from Instagram Reels (or any yt-dlp-supported URL) using yt-dlp and OpenAI Whisper locally.

## Requirements

- `yt-dlp` — downloads video/audio (`brew install yt-dlp`)
- `whisper` — transcribes audio (`pip install openai-whisper`)
- `ffmpeg` — audio conversion (`brew install ffmpeg`)
- Chrome browser logged into Instagram (used for cookie auth)

## Output Structure

All transcriptions are saved to:
```
/Users/mohannadarbaji/Desktop/Claude Code/Instragram Transcriptions/<descriptive-folder-name>/
  transcript.md   — URL, full transcript, and summary in one file
```

The subfolder name should be a short, descriptive title derived from the summary (e.g. `Amdahls Law - AI Moats Shift`). Use title case, keep it under ~60 chars, no special characters besides hyphens and spaces.

## Instructions

### Step 1 — Check dependencies
```bash
which yt-dlp && which whisper && which ffmpeg
```
If any are missing, install them before proceeding.

### Step 2 — Download audio and transcribe
```bash
rm -f /tmp/reel.mp3 /tmp/reel.txt
yt-dlp "INSTAGRAM_URL" --cookies-from-browser chrome -x --audio-format mp3 -o /tmp/reel.mp3 && whisper /tmp/reel.mp3 --model small --language en --output_format txt --output_dir /tmp
```

### Step 3 — Read transcript, generate summary, and save
Read the transcript from `/tmp/reel.txt`, then:

1. Write a 2-3 sentence summary
2. Derive a short descriptive folder name from the summary (title case, under ~60 chars, no special chars besides hyphens and spaces)
3. Create the output folder and save `transcript.md`:

```bash
FOLDER_NAME="<Descriptive Title From Summary>"
OUTPUT_DIR="/Users/mohannadarbaji/Desktop/Claude Code/Instragram Transcriptions/$FOLDER_NAME"
mkdir -p "$OUTPUT_DIR"
```

Format for `transcript.md`:
```
# <Descriptive Title>

**URL**: <original-url>
**Reel ID**: <reel-id>

## Transcript
<full transcript text>

## Summary
<2-3 sentence summary of the reel content>
```

Save it to `"$OUTPUT_DIR/transcript.md"`, then present the transcript and summary to the user.

## Notes

- If Whisper fails with an SSL error on first run, fix it with:
  ```bash
  /Applications/Python\ 3.13/Install\ Certificates.command
  ```
- For faster transcription on longer videos, use `--model tiny` (less accurate) or `--model medium` (more accurate, slower)
- Works with any URL yt-dlp supports: TikTok, YouTube Shorts, Twitter/X, etc.

## Example triggers

- "Transcribe this Instagram reel: [URL]"
- "What is this video about? [URL]"
- "Summarize this reel for me"
- "Can you transcribe and summarize this Instagram video?"
