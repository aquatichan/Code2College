# Scentasy
> A fragrance finder — search any perfume and see how it actually wears.

Search a fragrance by name and get back more than a product page: a radar chart of
its main accords, its note pyramid drawn as packed circles, how it ranks across
seasons and occasions, and how long it actually lasts on skin.

Built as a full-stack app — a React front end talking to an Express server that
holds the Fragella API key, so the key never ships to the browser.

## How it works

1. **You search.** The React client posts your query to its own server at
   `/api/fragrances`.
2. **The server calls Fragella.** It attaches the API key server-side and forwards
   the request, so the key stays out of the client bundle where anyone could read it.
3. **The card renders the data.** Accord strengths become a radar shape, the note
   pyramid becomes a packed-circle chart sized by tier, and the season/occasion
   scores become bar charts.

The charts are hand-rolled SVG rather than a charting library — only the
circle-packing layout pulls in a dependency (`d3-hierarchy`), since that's the one
piece with a non-trivial algorithm behind it.

## Setup

The server needs a Fragella API key.

```bash
cd app/server
cp .env.example .env      # then open .env and paste in your real key
npm install
```

```bash
cd app/client
npm install
```

## Run

Both halves need to be running. In two terminals:

```bash
# Terminal 1 — API server on :8080
cd app/server
npm run devStart         # or `npm start` for no auto-reload
```

```bash
# Terminal 2 — client on :3000
cd app/client
npm run dev
```

Open http://localhost:3000. The client dev server proxies `/api` through to
:8080, so both halves work together without any CORS setup.