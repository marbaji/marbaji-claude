---
name: watch-video-url
description: Use when the user shares a video URL (Instagram Reel, TikTok, YouTube Short, X/Twitter video, or anything yt-dlp supports) and wants it watched, transcribed, or summarized. Downloads the video with yt-dlp (no browser cookies by default, so no Keychain prompt), watches it with the claude-video-vision video_watch tool (frames plus a timestamped transcript), and saves a transcript.md under 20-areas/video-transcriptions/. Successor to instagram-transcribe (renamed 2026-09-11).
---

# Watch a video URL

Downloads a video from a URL and watches it: frames for what is on screen, a timestamped transcript for what is said. Works for Instagram Reels, TikTok, YouTube Shorts, X/Twitter and any other site yt-dlp supports.

## Requirements

- `yt-dlp` and `ffmpeg` (`brew install yt-dlp ffmpeg`)
- The `claude-video-vision` plugin, which provides the `video_watch` and `video_info` MCP tools (it transcribes with Whisper itself; no separate `whisper` install is needed)

## Output structure

All transcriptions are saved to:
```
/Users/mohannadarbaji/Desktop/Claude Code/20-areas/video-transcriptions/<Descriptive Title>/
  transcript.md   — URL, transcript, what is on screen, and summary in one file
```

**Never write to `~/Desktop/Claude Code/` root.** Transcriptions are an *area* (ongoing, no completion state), so they live under `20-areas/` per the PARA split of that folder. `20-areas/video-transcriptions/` holds the whole back catalog, including everything the old `instagram-transcriptions` folder held (renamed 2026-09-11 when the skill went generic). Area folders are plain lowercase slugs; the workspace-invariant hook flags any other name. Source: Mo, 2026-09-01, after two reels landed in a root-level duplicate folder that had to be merged back by hand; re-fixed 2026-09-09 after one reel landed in a re-created misspelled folder.

The subfolder name is a short descriptive title derived from the summary (e.g. `Amdahls Law - AI Moats Shift`). Title case, under ~60 characters, no special characters besides hyphens and spaces.

## Instructions

### Step 1 — Check dependencies
```bash
which yt-dlp && which ffmpeg
```
Install anything missing before proceeding. If the video tools are missing from the deferred tool list, the plugin is not installed; say so rather than falling back to a hand-rolled pipeline.

### Step 2 — Download the video (no cookies)
```bash
S="<session scratchpad directory, from the system prompt>"
rm -f "$S/video.mp4"
yt-dlp "VIDEO_URL" -o "$S/video.mp4" -q
yt-dlp "VIDEO_URL" --skip-download --print "%(uploader)s | %(title)s" --print "%(description)s"
```
The second command fetches the poster's handle and caption for attribution in `transcript.md`.

**Do not pass `--cookies-from-browser chrome`.** Chrome encrypts its cookie database with a key held in the macOS Keychain ("Chrome Safe Storage"), and reading it pops a password dialog on the Mac's screen. From the phone that dialog is invisible, and Mo had to remote in and type his login password to clear it. Public videos download without any cookies (verified 2026-09-11 on an Instagram Reel: full download, no prompt).

**Fallback, only when the download fails with a login or rate-limit message** ("login required", "Requested content is not available", "rate-limit reached"), in this order:

1. A cookie jar file, if it exists: `yt-dlp "VIDEO_URL" --cookies "$HOME/.config/yt-dlp/cookies.txt" -o "$S/video.mp4"`. To create it once (needs one Keychain approval, done at the Mac): `yt-dlp --cookies-from-browser chrome --cookies "$HOME/.config/yt-dlp/cookies.txt" --skip-download "https://www.instagram.com/"`. yt-dlp writes the jar to that file on exit; every later run reads the file and never touches the Keychain. Keep the file `chmod 600` and outside any repo.
2. Firefox cookies, if Mo is logged into the site there: `--cookies-from-browser firefox`. Firefox stores cookies unencrypted, so no Keychain prompt.

If neither works, report the exact yt-dlp error and stop; do not retry the Chrome flag.

### Step 3 — Watch it
MCP tools are deferred. Load the two you need in one call:

```
ToolSearch: select:mcp__plugin_claude-video-vision_claude-video-vision__video_info,mcp__plugin_claude-video-vision_claude-video-vision__video_watch
```

Then:

1. `video_info` on `$S/video.mp4` to get the duration.
2. `video_watch` on the same path. Defaults for a short social video (under ~3 minutes): `fps: "auto"`, `resolution: 512`, `frame_mode: "images"`. Use `resolution: 1024` when on-screen text matters (a screen recording, a slide, a tweet being read out). For a video longer than 30 seconds the tool's own guidance says to call `video_analyze` first for scene changes and silence, then set `segments` from that.
3. Read both channels. The transcript comes back with timestamps; the frames show what the transcript is talking about. For a reel that is half on-screen content (a demo, a game, a chart), the frames are the half the old audio-only pipeline missed.

### Step 4 — Save `transcript.md` and report
Write a 2 to 3 sentence summary, derive the folder name from it, then:

```bash
FOLDER_NAME="<Descriptive Title From Summary>"
OUTPUT_DIR="/Users/mohannadarbaji/Desktop/Claude Code/20-areas/video-transcriptions/$FOLDER_NAME"
mkdir -p "$OUTPUT_DIR"
```

Format for `transcript.md`:
```
# <Descriptive Title>

**URL**: <original-url>
**Video ID**: <platform id, e.g. the Instagram shortcode or TikTok numeric id>
**Posted by**: <uploader handle> — <caption, if any>

## Transcript
<full transcript text, keeping the tool's timestamps>

## On screen
<3 to 8 lines: what the frames show that the audio alone would not tell you — text on screen, a demo, a chart, a product, a face reading a tweet. Skip lines that only restate the transcript.>

## Summary
<2 to 3 sentence summary of the video>
```

Save it to `"$OUTPUT_DIR/transcript.md"`, then present the transcript, the on-screen notes and the summary to the user. The downloaded mp4 stays in the scratchpad; do not copy it into the area.

## Notes

- If `video_watch` reports missing dependencies, call `video_setup` from the same plugin (or run `/claude-video-vision:setup-video-vision`).
- The video tools accept YouTube URLs directly, but not Instagram or TikTok URLs, which is why yt-dlp still does the download for everything.
- For a long video (a talk, a podcast), lower the frame rate (`fps: 0.1` to `0.5`) and read `audio.warnings` in the result for chunk-boundary notes.

## Example triggers

- "Transcribe this Instagram reel: [URL]"
- "What is this TikTok about? [URL]"
- "Watch this and tell me what's on screen: [URL]"
- "Summarize this video for me"
