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
/Users/mohannadarbaji/Desktop/Claude Code/Skills/instagram-transcribe/Instragram Transcriptions/<reel-id>/
  transcript.md   — URL, full transcript, and summary in one file
```

The subfolder name should be the reel ID extracted from the URL (e.g. `DVtxgZODjSF`).

## Instructions

### Step 1 — Check dependencies
```bash
which yt-dlp && which whisper && which ffmpeg
```
If any are missing, install them before proceeding.

### Step 2 — Extract reel ID and set up output folder
Extract the reel ID from the URL (the segment after `/reel/`), then create the output folder:
```bash
REEL_ID="<id-from-url>"
OUTPUT_DIR="/Users/mohannadarbaji/Desktop/Claude Code/Skills/instagram-transcribe/Instragram Transcriptions/$REEL_ID"
mkdir -p "$OUTPUT_DIR"
```

### Step 3 — Download audio and transcribe
```bash
yt-dlp "INSTAGRAM_URL" --cookies-from-browser chrome -x --audio-format mp3 -o /tmp/reel.mp3 && whisper /tmp/reel.mp3 --model small --language en --output_format txt --output_dir /tmp
```

### Step 4 — Read transcript and create transcript.md
Read the transcript from `/tmp/reel.txt`, then create a single `transcript.md` file:

```
# Reel: <reel-id>

**URL**: <original-instagram-url>

## Transcript
<full transcript text>

## Summary
<2-3 sentence summary of the reel content>
```

Save it to `"$OUTPUT_DIR/transcript.md"`.

Then present the transcript and summary to the user.

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
