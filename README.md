# C and Embedded C notes (static site)

Your four Word documents as a fast, searchable reading site. No server code needed.

## Deploy on Render (free)
1. Create a GitHub repository (for example `c-notes`) and upload everything in this folder to it.
2. On https://render.com choose New > Static Site and connect that repository.
3. Leave Build Command empty and set Publish Directory to `public` (render.yaml sets this for you if you use a Blueprint).
4. Click Create Static Site. In about a minute you get a URL like https://c-embedded-notes.onrender.com

Every push to GitHub redeploys automatically.

## Updating the notes
Replace the files in `docs/` with your edited Word files (same names), then run:

    pip install lxml
    python build.py

Commit and push. This regenerates everything in `public/content`.

## Features
Search across all four documents (press / to focus), contents list that follows your position, C syntax colours with Copy buttons,
light and dark mode, remembers your last document and scroll position, mobile friendly, link to download each original .docx.
