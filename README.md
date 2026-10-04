# Is it AI? — AI Content Detector

Detects AI-generated content across text, images, and video. FastAPI
backend, React frontend.

## Setup

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Visit http://localhost:8000/health and http://localhost:8000/docs.

You also need the **FFmpeg system binary** installed (not just a Python
package) for the video pipeline:
- Windows: `winget install ffmpeg`
- Mac: `brew install ffmpeg`
- Linux: `sudo apt install ffmpeg`

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Visit http://localhost:5173.

## What's built so far

**Detection pipelines** (Tasks 1-4): text (RoBERTa classifier + perplexity +
burstiness), image (ViT classifier + FFT frequency analysis), video (frame
sampling via OpenCV, reusing the image pipeline per frame, run as a
background job you poll).

**Dashboard** (Task 5): media type tabs, drag-and-drop upload with
image/video preview, a color-coded verdict band, a signal breakdown table,
plain-language risk flags, light/dark theme toggle.

**Hardening** (Task 6): rate limiting (20 req/min/IP on `/analyze/*`),
result caching by content hash, configurable CORS via `ALLOWED_ORIGINS` env
var, a global error handler that never leaks stack traces, a text length cap.

**Deployment prep** (Task 7): `backend/Dockerfile` (includes FFmpeg),
frontend reads `VITE_API_BASE_URL` in production instead of the local dev
proxy. See the Azure deployment section below.

**Login system** (Task 8 — just added):
- Email + password signup/login, SQLite-backed (`backend/app/db.py`,
  stdlib only, no new dependencies)
- Passwords hashed with PBKDF2-SHA256 (stdlib `hashlib`), never stored
  in plain text
- Session tokens (not JWTs) stored server-side so logout actually revokes
  them — `backend/app/services/auth.py`
- All three `/analyze/*` endpoints now require a valid session token,
  enforced in the backend itself (`Depends(get_current_user)`), not just
  hidden in the UI — try calling `/analyze/text` without a token and
  you'll get a 401
- Frontend: Log in / Sign up buttons top-right, a modal for both, the
  Analyze button is disabled with an inline prompt when logged out, and
  the session persists across page refreshes via `localStorage`

**Models upgraded (just done)**: both the text and image classifiers were
swapped for more current, better-documented alternatives:
- Text: `roberta-base-openai-detector` → `ogmatrixllm/glyph-v1.1` (GLYPH).
  The old model was OpenAI's own GPT-2-era detector from 2019 — multiple
  independent sources confirm it performs poorly on ChatGPT/GPT-4-era text,
  which is almost certainly what anyone testing your tool will paste in.
  GLYPH is documented across 14 model families spanning GPT-2 through GPT-4.
- Image: `umm-maybe/AI-image-detector` → `Organika/sdxl-detector` (a Swin
  Transformer, not ViT, but same drop-in usage pattern). Note: an initial
  attempt to use `husseinelsaadi/aidetect-vit-b16` failed — that repo turned
  out to be a raw research artifact dump (experiment checkpoints in
  subfolders), missing the `preprocessor_config.json` a real model needs.
  `Organika/sdxl-detector` is confirmed properly packaged and is itself a
  fine-tune of the original model, specifically retrained on SDXL-generated
  images. Its own model card is upfront that it's optimized for SDXL
  specifically and may underperform on other generators (Midjourney, Flux,
  older GANs) — a real improvement, not a universal fix.
- Both pipelines' weighting shifted from ~70/30 to 85/15 in favor of the
  classifier, since the new models are documented as meaningfully more
  reliable standalone than the heuristic signals (perplexity/burstiness for
  text, FFT for images) ever were. The FFT weight in particular was an
  uncalibrated guess from the start and likely contributed to wrong
  verdicts as much as the old image model did.
- First request after this change will re-download new model weights
  (a few hundred MB to ~1GB) - same one-time cost as before, cached after.

### Try the login flow
1. `npm run dev` + `uvicorn app.main:app --reload`
2. Click "Sign up" top-right, create an account (password min 8 characters)
3. Notice the Analyze button is now enabled — try logging out and you'll
   see it disable again with a prompt
4. Your session persists if you refresh the page

A new `backend/app_data.db` SQLite file is created automatically on first
run — it's gitignored, so each environment (your PC, Azure) has its own.

## Deploying to Azure (Azure for Students)

1. Push this repo to GitHub (`.gitignore` already excludes `venv/`,
   `node_modules/`, and `*.db`)
2. Azure Portal → Create a resource → Web App → Publish: **Container** →
   Linux → Basic B1 plan → point at your GitHub repo's `backend/` folder
3. In the Web App's Configuration → Application settings, add:
   ```
   ALLOWED_ORIGINS = https://your-app-name.vercel.app
   ```
4. Deploy the frontend to Vercel, root directory `frontend/`, with env var:
   ```
   VITE_API_BASE_URL = https://your-app-name.azurewebsites.net
   ```
5. Visit your Vercel URL, confirm "Backend connected," sign up, run a test
   through each media type

**Note**: SQLite lives inside the container's filesystem — it resets on
redeploy/restart unless you mount persistent storage. Fine for a demo;
flag it if you need accounts to survive indefinitely.

## Task 9 — Scan history (just added)

- Every text/image/video analysis is now saved to a `scans` table, tied to
  the logged-in user. Only the **result** is stored (score, confidence,
  breakdown, a short label) — never the raw uploaded file, keeping storage
  tiny and sidestepping privacy concerns.
- Capped at 50 stored scans per user (oldest pruned automatically); the
  dashboard displays the 10 most recent.
- New endpoints: `GET /scans` (list recent) and `GET /scans/{id}` (full
  detail of one past scan), both login-gated to the owning user only.
- Frontend: a "Recent scans" panel appears between the upload box and the
  results area once you're logged in. Click any entry to reload that full
  result into the results view below — handy for re-checking something
  without re-running it, or showing a judge a scan from earlier in your demo.
- Video scans are recorded once the background job finishes (or instantly,
  if the video hit the cache from an identical prior upload).

### Try it
Log in, run one scan of each type, and watch "Recent scans" populate.
Click an older entry — the results panel below updates to show it.

### Also this session
- Text detector swapped `roberta-base-openai-detector` → `ogmatrixllm/glyph-v1.1`
  (GLYPH) — the old model was GPT-2-era and unreliable against modern LLM output.
- Image detector swapped `umm-maybe/AI-image-detector` → `Organika/sdxl-detector`
  (a properly packaged, SDXL-focused fine-tune; an initial attempt at a
  different model failed because that repo was missing required files).
- Both pipelines rebalanced to weight the classifier more heavily (85/15)
  over the heuristic signals.
- `requirements.txt` gained `protobuf` and `sentencepiece`, required by
  GLYPH's tokenizer.
- Text input now shows a word count instead of a character count.

## Forgot password, profile page, and thumbnails (just added)

**Forgot password (Gmail SMTP)**:
- New endpoints: `POST /auth/forgot-password` (always returns the same
  generic message whether or not the email is registered, to avoid leaking
  which emails have accounts) and `POST /auth/reset-password`.
- `backend/app/services/email.py` sends via Gmail SMTP using stdlib
  `smtplib` — no new dependency. **Without configuration, it logs the
  reset link to your console instead of sending** — so the flow is fully
  testable locally with zero setup. To actually send real email, set two
  environment variables:
  ```
  GMAIL_ADDRESS=youraddress@gmail.com
  GMAIL_APP_PASSWORD=your-16-character-app-password
  ```
  The app password comes from Google Account → Security → 2-Step
  Verification (must be enabled first) → App passwords. Your regular Gmail
  password will NOT work here — Google blocks that for SMTP.
- Also set `FRONTEND_URL` (defaults to `http://localhost:5173`) so the
  emailed link points at the right place — set this to your Vercel URL
  once deployed.
- Resetting a password invalidates all existing sessions for that account.
- Frontend: "Forgot password?" link in the login modal → email form →
  generic confirmation message. Opening the emailed link (`?resetToken=...`)
  automatically shows a "set new password" modal.

**Profile page**: scan history moved off the main dashboard onto a
dedicated profile view. Click your email (top-right) to go there, click
the "Is it AI?" title to come back. No routing library used — just a
simple view-state toggle and a URL query param for the reset-password link.

**Inline result expansion**: clicking a history entry now expands the full
result directly under that item, instead of loading it into a separate
section elsewhere on the page.

**Thumbnails in history**: image and video scans now show a small preview
thumbnail. These are deliberately NOT full copies of your uploads — each
one is resized to a max of 160px and JPEG-compressed to quality 60 before
being stored, keeping every thumbnail in the single-digit KB range
regardless of the original file size. Text scans have no thumbnail (nothing
visual to show). If you already have an `app_data.db` from before this
change, it's migrated automatically on next startup — no need to delete it.

**Rate limit**: default raised from 20 to 100 requests/minute for smoother
live demos. Edit `backend/app/middleware/rate_limit.py`, lines 18-19
(`MAX_REQUESTS` and `WINDOW_SECONDS`) directly if you want a different cap.

## PDF extraction fix: LaTeX documents were getting falsely flagged (just fixed)

Real bug caught through actual testing: `pypdf` inserts a line break after
every visual line of the PDF, not every paragraph. LaTeX's heavy
justification/word-wrapping meant a single sentence often extracted as
several line-broken fragments, frequently with words split by a hyphen at
the break (`informa-\ntion`). That artificially mangled text doesn't
resemble anything either the classifier or the perplexity model were
trained on, which was pushing normal LaTeX-written lab reports toward "AI."

Fix: `normalize_extracted_text()` in `pdf_extraction.py` rejoins
hyphen-split words and collapses mid-paragraph line wraps into spaces,
while preserving real paragraph breaks. It runs AFTER reference-stripping
(which needs the original line breaks to find the heading) and BEFORE
scoring. Re-test a LaTeX-compiled report that was flagged before — it
should score meaningfully differently now.

## Task 11 — Sentence-level highlighting (just added)

- Text and PDF results now include a per-sentence AI-likelihood score,
  shown as a highlighted-text view instead of plain text.
- Scored in ONE batched forward pass through the classifier (not one call
  per sentence) — meaningfully faster on CPU-only hosting.
- Only sentences scoring above 60% get any highlight at all, with a
  proportional tint from there to 100% — keeps the view from turning into
  a wall of color, and draws the eye to what actually stood out, which
  matters most for the research-paper use case.
- Capped at 80 sentences per document for response-time reasons; longer
  documents get `sentence_highlighting_partial` flagged, and the overall
  score above the highlighted text still reflects the complete text either way.
- Hover any sentence to see its exact percentage.
- Stored in scan history too (new `sentences` column, auto-migrated on
  existing databases), so reopening a past scan still shows highlighting.

### Try it
Paste or upload something with an obvious mix of human and AI-sounding
sentences and see whether the highlighting lines up with what you'd expect.

## Task 12 — Two-document similarity check (just added)

A new **Compare** tab, architecturally separate from the other four since
it takes two files in and returns a similarity score, not an AI-probability
— not retrofitted into the existing DetectionResult shape.

- Compares two uploaded PDFs **directly against each other only** — not
  against the web or any corpus. Honestly scoped: good for "did these two
  lab reports/assignments overlap," not a substitute for real plagiarism
  detection against the internet.
- Two signals, both dependency-free (no new packages):
  1. **Shingle/Jaccard similarity** — the headline score. Splits each
     document into overlapping 5-word sequences and measures the overlap.
     Catches copy-paste-with-light-editing well; will NOT catch a fully
     paraphrased passage that reuses no original wording — a real limit,
     stated plainly in the result's disclaimer.
  2. **Matching passages** — the actual overlapping text (via `difflib`),
     shown verbatim so you can see exactly what matched rather than trust
     a bare percentage.
- Both PDFs go through the same extraction/reference-stripping/
  normalization pipeline as the regular PDF checker, so the LaTeX
  line-wrap fix applies here too.
- Saved to scan history as its own `similarity` type, reusing the same
  generic storage (no new DB columns) — shows up in your profile's
  "Recent scans" with its own comparison-specific view when expanded.

### Try it
Upload two different PDFs (should show low overlap), then try the same
PDF twice (should show ~100% overlap) to sanity-check both ends of the scale.

## Paraphrase detection (just added)

Extends the Compare tab with a second, independent signal alongside the
literal shingle-overlap check from Task 12.

- **New dependency**: `sentence-transformers` (reuses the torch already
  installed; downloads a small ~80MB model, `all-MiniLM-L6-v2`, on first use)
- Compares every sentence in Document A against every sentence in Document B
  using sentence embeddings (meaning-based vectors, not word-based), batched
  for speed
- Only reports a pair as a "paraphrase match" when it's semantically close
  (cosine similarity > 0.72) **and** has low literal word overlap (<0.25)
  — a pair that's similar on both counts is just a regular match the
  literal check already found, and isn't reported twice
- Shown as a clearly separate section in the results, never blended into
  the literal similarity percentage — "same wording" and "same meaning"
  are different claims and conflating them would be misleading
- Honest about its own limits in both directions: two independently
  written reports on the same topic may share meaning without copying
  (false positive risk), and a thoroughly reworded passage can still slip
  past it (false negative risk)

### Try it
Write a short paragraph, then rephrase it entirely in your own words in a
second document — the literal score should stay low while the paraphrase
section should catch the match.

## Task 13 — Downloadable PDF result reports (just added)

The last item on the original feature list.

- **New dependency**: `reportlab` (the standard library for generating
  PDFs from scratch — different from `pypdf`, which only reads/edits
  existing ones)
- A "Download PDF report" button now appears on every result — fresh
  results and past scans from history alike, for every media type
  including similarity comparisons
- Each report includes: the headline score, a signal breakdown table, risk
  flags, and (for text/PDF) either the sentence-level highlighted view or
  the extracted text, or (for comparisons) matching passages and
  paraphrase matches
- Generated entirely server-side in memory — nothing written to disk,
  nothing to clean up
- Tested directly in this session: generated both a detection-style and a
  similarity-style report from realistic sample data, including a
  deliberately tricky case with `<`, `&`, `>` characters in the scored
  text (which would break the PDF library's markup parser if text weren't
  properly escaped) — both came back as valid, correctly-rendering PDFs.

### Try it
Run any analysis, click "Download PDF report" on the result. Also try it
from your profile's scan history — expand a past scan and the same button
is there.

## All 13 tasks complete

Every feature from the original list is built: text/image/video/PDF
detection, a dashboard with previews and theming, login with password
reset, scan history with thumbnails, sentence-level highlighting,
two-document comparison (literal + paraphrase detection), and downloadable
PDF reports. What's left is deployment — Azure for the backend, Vercel for
the frontend — both prepped and documented above, waiting on your Student
Pack credit.
