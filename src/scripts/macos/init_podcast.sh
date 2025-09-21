#!/bin/bash

# init_podcast.sh
# Initializes the directory structure and RSS feed for a new novel podcast.

# Exit on error
set -e

# --- Configuration ---
# The root directory for all podcast projects
PODCASTS_ROOT_DIR="./podcasts"
# The base URL where the podcast files will be hosted
HOST_BASE_URL="https://geonwprj.github.io/novels/podcasts"

# --- Script ---
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <\"Novel Name\"> <\"Podcast Description\">"
    exit 1
fi

NOVEL_NAME=$1
PODCAST_DESCRIPTION=$2
NOVEL_DIR="$PODCASTS_ROOT_DIR/$NOVEL_NAME"
EPISODES_DIR="$NOVEL_DIR/episodes"
RSS_ITEMS_DIR="$NOVEL_DIR/rss_items"
RSS_FILE="$NOVEL_DIR/rss.xml"

# --- Create Directories ---
echo "Initializing directory structure for podcast: '$NOVEL_NAME'..."
mkdir -p "$EPISODES_DIR"
mkdir -p "$RSS_ITEMS_DIR"
echo "Directories created at $NOVEL_DIR"

# Construct the full URL for this specific novel
NOVEL_URL="$HOST_BASE_URL/$NOVEL_NAME"

# --- Create RSS Template ---
echo "Creating RSS feed template at $RSS_FILE..."

cat > "$RSS_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>$NOVEL_NAME</title>
    <link>$NOVEL_URL</link>
    <description><![CDATA[$PODCAST_DESCRIPTION]]></description>
    <content:encoded><![CDATA[$PODCAST_DESCRIPTION]]></content:encoded>
    <language>zh-cn</language>
    <itunes:author>AI Generated</itunes:author>
    <itunes:summary><![CDATA[$PODCAST_DESCRIPTION]]></itunes:summary>
    <itunes:explicit>no</itunes:explicit>
    <itunes:category text="Arts"/>

    <!-- EPISODE_ITEMS_PLACEHOLDER -->

  </channel>
</rss>
EOF

echo "
Initialization complete."
echo "Next, use ./create_episode.sh or ./batch_create.sh to add episodes."
