# Portfolix — GitHub Portfolio Auto-Exporter

<img width="752" height="1225" alt="Screenshot 2026-07-07 at 3 08 20 PM" src="https://github.com/user-attachments/assets/ba5a1ce4-b602-48ed-b46a-9aefb6c6b50d" />

Query the **public** GitHub API for your public repos, top projects, and language
breakdown — then turn that into a **portfolio site, technical CV, cover letter, or
skills brag sheet** you fully control and customize in the browser, right before
you go job hunting.

**Two parts, one data file:**

1. **A Python CLI** (`generate.py`) fetches your GitHub data, optionally runs it
   through Gemini for polished copy, and writes **`output/data.json`**.
2. **A static landing site** (`site/`) reads that `data.json` and lets you pick
   documents, toggle AI copy, apply an AI "beautify" style, preview, and 
   **live-edit the HTML/CSS** of any document — all in the browser, no server.

## Highlights

- 💼 **Studio landing page** — pick one or many documents (multiselect), toggle
  AI-enhanced copy, then generate them all at once.
- 📄 **Four document types** — Portfolio Site, Technical CV, Cover Letter,
  Skills/Brag Sheet.
- 🎨 **Portfolio** — avatar, bio, links (auto-labeled LinkedIn / Website), stat
  tiles, a language bar **with a labeled legend**, and featured project cards.
- ✨ **Beautify with AI** — a one-click toggle that applies an AI-generated style
  pack (accent, fonts, radii) baked into `data.json` when a Gemini key is set.
- ✎ **Live editor** — a sliding, resizable sidebar to edit any document's HTML &
  CSS and see changes instantly. Reset reverts to the generated version.
- 🌌 **Animated node background** that responds to your cursor and follows the
  light/dark theme.
- 🤖 **Optional Gemini AI** — polished bio, project one-liners, an about/ambitions
  narrative, a drafted cover letter, a quantified brag sheet, and the beautify
  style pack. Everything works without a key.

## Setup & Usage

### 1. Run the app

```bash
cd Portfolix
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # core + optional Gemini
cp .env.example .env                 # fill in the values
```

### 2. Fetch your data

```bash
python generate.py --username YOUR_NAME        # writes output/data.json
python generate.py                             # uses GITHUB_USERNAME from .env
python generate.py -u YOUR_NAME --no-ai        # skip Gemini even if key is set
```

### 3. Open the Studio

The site loads `data.json` over HTTP, so serve the folder (not `file://`):

```bash
python -m http.server 8000
# then open http://localhost:8000/site/
```

Pick your documents, toggle options, hit **Generate**, and export. Use the ✎
button (bottom-right) to open the live editor.

## Configuration (`.env`)

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `GITHUB_USERNAME` | Optional | Default username (override with `--username`). |
| `GITHUB_TOKEN` | Optional | Portfolix uses only the public GitHub API. A token *only* raises the rate limit (60 → 5000 req/hr). Leave blank unless you hit the limit. |
| `GEMINI_API_KEY` | Optional | Enables AI copy (bio, narrative, cover letter, brag sheet), the site's **Beautify with AI ✨** style pack, and CLI `--beautify`. |

> Gemini key: <https://aistudio.google.com/app/apikey>

## Project structure

```
Portfolix/
├── generate.py             # CLI entry point → writes output/data.json (+ optional exports)
├── portfolix/
│   ├── github_client.py    # public REST API only (repos/languages/stats) — no token
│   ├── ai_enhancer.py      # optional Gemini: bio, summaries, narrative, cover letter, brag sheet, style pack
│   └── builder.py          # renders Jinja templates → standalone HTML exports
├── templates/              # Jinja templates for the CLI's HTML exports
│   ├── portfolio.html.j2
│   └── cv.html.j2
├── site/                   # the static Studio landing site (loads output/data.json)
│   ├── index.html
│   ├── styles.css          # Studio UI shell (theme-aware)
│   ├── app.js              # orchestration: picker, generate, editor, AI beautify
│   ├── docs.js             # in-browser document renderers (portfolio/CV/cover/brag)
│   └── background.js       # animated node background
├── output/                 # generated data.json + optional exports (gitignored)
├── requirements.txt
└── .env.example
```

## How it fits together

```
 python generate.py ──► public GitHub API ──► (optional Gemini) ──► output/data.json
                                                                          │
                              site/ (static, no server logic) ────────────┘
                              reads data.json → renders documents in-browser,
                              HTML preview, AI beautify, live HTML/CSS editing
```

Re-run `generate.py` any time your GitHub changes; refresh the Studio to pick up
the new `data.json`.
