# Novel Processing and Podcasting System

This project provides a comprehensive system for processing novel content, translating it using AI, and publishing it as both a GitHub Pages website and a podcast.

## Features

- **Automated Translation:** Monitors a `processing` directory for new novel chapters in JSON format and uses an LLM to translate them into Cantonese.
- **GitHub Pages Publishing:** Automatically publishes the translated HTML files to a GitHub Pages website.
- **Podcast Generation:** Converts the translated text into audio files and generates a podcast RSS feed for subscription.
- **Flexible Branching:** Uses separate branches for source code (`main`), website content (`pages`), and novel content (`books`).

## How It Works

### 1. Translation

1.  **Upload Content:** Place JSON files containing novel chapters into the `processing` directory on the `books` branch.
2.  **Automated Processing:** A GitHub Actions workflow (`translate.yml`) is triggered on push. It processes each new JSON file, generates an HTML file, and commits it to the `pages` branch.
3.  **Source Deletion:** After successful processing, the original JSON file is removed from the `books` branch.

### 2. Podcasting

This is a two-step process that involves creating individual episodes and then building the final RSS feed.

#### a. Create Podcast Episode

1.  **Manual Trigger:** The episode creation is triggered manually through the `create_podcast_episode.yml` GitHub Actions workflow.
2.  **Inputs:** The workflow requires the novel name and the chapter index.
3.  **Episode Generation:** The workflow uses the `create_episode.sh` script to fetch the translated HTML content from the `pages` branch, convert it to an MP3 audio file using the `say` command on a macOS runner, and create an individual RSS item XML file.
4.  **Publishing:** The generated MP3 and XML files are committed to the `pages` branch.

#### b. Build Podcast Feed

1.  **Automated Trigger:** The `build_podcast_feed.yml` workflow is triggered automatically when new episode XML files are pushed to the `podcasts/` directory on the `pages` branch.
2.  **RSS Feed Generation:** The workflow uses the `build_rss.sh` script to assemble the final `rss.xml` file from the individual episode items.
3.  **Publishing:** The updated `rss.xml` file is committed to the `pages` branch.

## Project Structure

```
/
├── .github/
│   ├── scripts/
│   │   └── build_rss.sh
│   └── workflows/
│       ├── process_files.yml
│       ├── translate.yml
│       ├── create_podcast_episode.yml
│       └── build_podcast_feed.yml
├── processing/         # (on books branch) Directory for raw novel content in JSON format
├── src/
│   ├── app.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── llm.py
│   │   └── translate.py
│   └── scripts/
│       └── macos/
│           ├── init_podcast.sh
│           └── create_episode.sh
├── templates/          # Jinja2 templates for generating HTML files
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

## Usage

### Translation

1.  Ensure your novel content is in the correct JSON format (see `translate.py` for details).
2.  Push the JSON files to the `processing` directory on the `books` branch.
3.  The `translate.yml` workflow will automatically process the files and publish the HTML to the `pages` branch.

### Podcasting

1.  **Initialize a new podcast (if needed):** Run the `init_podcast.sh` script locally to create the necessary directory structure for a new novel.
2.  **Create an episode:**
    - Go to the "Actions" tab of your GitHub repository.
    - Select the "Create Podcast Episode" workflow.
    - Click "Run workflow".
    - Enter the novel name and chapter index.
3.  **Automatic Feed Update:** The `build_podcast_feed.yml` workflow will automatically run and update the RSS feed.

## Configuration

- **LLM Configuration:** The translation process requires LLM API credentials. These are configured as secrets and variables in your GitHub repository (`LLM_MODEL`, `LLM_PROMPT`, `LLM_TOKEN`, `LLM_URL`, `LLM_PROVIDER`).
- **Website URL:** The podcast scripts use the `HOST_BASE_URL` variable, which should be set to your GitHub Pages URL (`https://geonwprj.github.io/novels`).
