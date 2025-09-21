#!/bin/bash

# build_rss.sh
# Assembles the final RSS feed from all the individual episode item files.

# Exit on error
set -e

# Change to the script's directory AND THEN go to the project root.
# This makes all subsequent paths work reliably.
cd "$(dirname "$0")/../.."

# --- Configuration ---
PODCASTS_ROOT_DIR="./podcasts"

# --- Script ---
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <\"Novel Name\">"
    exit 1
fi

NOVEL_NAME=$1
NOVEL_DIR="$PODCASTS_ROOT_DIR/$NOVEL_NAME"
RSS_ITEMS_DIR="$NOVEL_DIR/rss_items"
RSS_FILE="$NOVEL_DIR/rss.xml"

PLACEHOLDER="<!-- EPISODE_ITEMS_PLACEHOLDER -->"

# --- Verify Podcast is Initialized ---
if [ ! -f "$RSS_FILE" ]; then
    echo "Error: RSS file for '$NOVEL_NAME' not found."
    echo "Please run ./src/local/init_podcast.sh '$NOVEL_NAME' first."
    exit 1
fi

# --- Main Process ---
echo "Building final RSS feed for '$NOVEL_NAME'..."

# Create a temporary file to hold all the episode items
COMBINED_ITEMS_FILE=$(mktemp)

# Check if there are any items to add
if [ -z "$(ls -A $RSS_ITEMS_DIR)" ]; then
   echo "Warning: No episode items found in $RSS_ITEMS_DIR. RSS feed will be empty."
else
    # Concatenate all item files into the temp file, newest first (version sort)
    cat $(ls -vr $RSS_ITEMS_DIR/*.xml) > "$COMBINED_ITEMS_FILE"
fi

# Use awk to replace the placeholder with the content of the combined items file
awk -v placeholder="$PLACEHOLDER" -v items_file="$COMBINED_ITEMS_FILE" \
    '$0 ~ placeholder { \
        while ((getline line < items_file) > 0) { \
            print line \
        } \
        next \
    } \
    { print }' "$RSS_FILE" > "$RSS_FILE.tmp" && mv "$RSS_FILE.tmp" "$RSS_FILE"

# Clean up the temporary file
rm "$COMBINED_ITEMS_FILE"

echo "
RSS feed built successfully!"
echo "Your final feed is ready at: $RSS_FILE"
