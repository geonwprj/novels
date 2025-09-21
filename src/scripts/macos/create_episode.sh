#!/bin/bash

# create_episode.sh
# Creates a single podcast episode (audio file and RSS item) from a novel chapter.

# Exit on error
set -e

# --- Configuration ---
PODCASTS_ROOT_DIR="./podcasts"
HOST_BASE_URL="https://geonwprj.github.io/novels/podcasts"
NOVEL_SOURCE_BASE_URL="https://geonwprj.github.io/novels"
SENTENCE_PAUSE_MS=500
WORD_PAUSE_MS=150

# --- Script ---
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <\"Novel Name\"> <Chapter Index>"
    exit 1
fi

NOVEL_NAME=$1
CHAPTER_INDEX=$(printf "%04d" "$2")

# --- Define Paths ---
NOVEL_DIR="$PODCASTS_ROOT_DIR/$NOVEL_NAME"
EPISODES_DIR="$NOVEL_DIR/episodes"
RSS_ITEMS_DIR="$NOVEL_DIR/rss_items"

SOURCE_URL="$NOVEL_SOURCE_BASE_URL/$NOVEL_NAME/$CHAPTER_INDEX.html"

# Create a temporary working directory for this chapter
TEMP_WORK_DIR=$(mktemp -d)

HTML_FILE="$TEMP_WORK_DIR/content.html"
TEXT_FILE="$TEMP_WORK_DIR/content.txt"
PAUSED_TEXT_FILE="$TEMP_WORK_DIR/content_paused.txt"
TEMP_AUDIO_FILE="$TEMP_WORK_DIR/audio.m4a"

# Final output files
FINAL_MP3_FILE="$EPISODES_DIR/$CHAPTER_INDEX.mp3"
EPISODE_XML_FILE="$RSS_ITEMS_DIR/$CHAPTER_INDEX.xml"

# --- Verify Podcast is Initialized ---
if [ ! -d "$NOVEL_DIR" ]; then
    echo "Error: Podcast for '$NOVEL_NAME' not found."
    echo "Please run ./init_podcast.sh '$NOVEL_NAME' first."
    exit 1
fi

# --- Main Process ---
echo "--- Processing Chapter $CHAPTER_INDEX for '$NOVEL_NAME' ---"

# 1. Fetch and Extract
echo "[1/5] Downloading and parsing content..."
curl -sL "$SOURCE_URL" -o "$HTML_FILE"
CHAPTER_TITLE=$(grep -o '<title>.*</title>' "$HTML_FILE" | sed 's/<title>//;s/}<\/title>//')
sed -n '/<article>/,/<\/article>/p' "$HTML_FILE" | sed 's/<[^>]*>/\n/g' | grep -v '^$' > "$TEXT_FILE"

# 2. Generate Audio
echo "[2/5] Generating speech audio..."
sed "s/。/。 [[slnc $SENTENCE_PAUSE_MS]]/g; s/！/！ [[slnc $SENTENCE_PAUSE_MS]]/g; s/？/？ [[slnc $SENTENCE_PAUSE_MS]]/g; s/ / [[slnc $WORD_PAUSE_MS]]/g" "$TEXT_FILE" > "$PAUSED_TEXT_FILE"
say --file-format=m4af --data-format=alac -o "$TEMP_AUDIO_FILE" -f "$PAUSED_TEXT_FILE"

# 3. Convert to MP3
echo "[3/5] Converting audio to MP3..."
/opt/homebrew/bin/ffmpeg -i "$TEMP_AUDIO_FILE" -c:a libmp3lame -q:a 5 "$FINAL_MP3_FILE"

# 4. Get Metadata for RSS
echo "[4/5] Gathering metadata for RSS feed..."
MP3_URL="$HOST_BASE_URL/$NOVEL_NAME/episodes/$CHAPTER_INDEX.mp3"
MP3_SIZE=$(stat -f %z "$FINAL_MP3_FILE")
MP3_DURATION=$(/opt/homebrew/bin/ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$FINAL_MP3_FILE")
PUB_DATE=$(date -R)

# 5. Create RSS Item XML
echo "[5/5] Creating RSS item file..."

# Read the full chapter text into a variable
DESCRIPTION_TEXT=$(cat "$TEXT_FILE")

cat > "$EPISODE_XML_FILE" << EOF
<item>
  <title>$CHAPTER_TITLE</title>
  <description><![CDATA[$DESCRIPTION_TEXT]]></description>
  <content:encoded><![CDATA[$DESCRIPTION_TEXT]]></content:encoded>
  <pubDate>$PUB_DATE</pubDate>
  <enclosure url="$MP3_URL" length="$MP3_SIZE" type="audio/mpeg" />
  <guid>$MP3_URL</guid>
  <itunes:summary><![CDATA[$CHAPTER_TITLE]]></itunes:summary>
  <itunes:duration>$MP3_DURATION</itunes:duration>
  <itunes:explicit>no</itunes:explicit>
</item>
EOF

# --- Cleanup ---
rm -r "$TEMP_WORK_DIR"

echo "--- Successfully created episode $CHAPTER_INDEX ---"

