# Optional AI assistant (Google Gemini)

**Why:** the “Ask” panel explains terms, results and failed checks. It never calculates, changes or approves anything; all numbers come from the engine.
**Required?** No. With it disabled the panel says so and everything else works.

## Steps
1. Sign in at https://aistudio.google.com/apikey with a Google account → **Create API key**. Use a separate key for Cable-N (do not reuse Track-N's).
2. Edit `backend/.env`:
   ```
   AI_ENABLED=true
   GEMINI_API_KEY=your-key
   GEMINI_MODEL=gemini-3.1-flash-lite
   ```
   `gemini-3.1-flash-lite` works on the no-card free tier; check the current model list in AI Studio if it is ever retired.
3. Restart the backend (`.\scripts\stop.ps1; .\scripts\start.ps1` or `docker compose up -d`).

## Test
- `http://localhost:8000/api/v1/assistant/status` → `"configured": true`.
- Open the site → **Ask** → “What is the grouping factor?” → an answer appears.

## Costs and limits
The free tier costs nothing but has quotas; with billing enabled you pay per token. Cable-N limits use to `AI_RATE_PER_MINUTE` (3) and `AI_DAILY_PER_IP` (20) per visitor and `AI_DAILY_GLOBAL` (500) provider calls per day per server process — lower them to cap spend. Set a budget alert in Google Cloud if billing is on.

## Privacy
The key stays on the server. A calculation is sent only when the visitor ticks “Share the current calculation”; the server recomputes it and sends inputs/results without project, client or site names. The privacy policy page states this.

## Disable
`AI_ENABLED=false` (or empty key) and restart.
