# What you need to configure yourself

The core website (all four calculators, reports, exports, validation, library, saved work) runs with **no keys, no accounts and no paid services**. Everything below is optional except item 1 for a public deployment.

| # | Item | Required? | File / variable | Cost |
|---|---|---|---|---|
| 1 | Public site URL | For production | `frontend/.env.production` → `VITE_SITE_URL` | – |
| 2 | Domain + HTTPS | For production | DNS + reverse proxy, see DEPLOYMENT.md | domain fee |
| 3 | Contact e-mail | Optional | `VITE_CONTACT_EMAIL` | – |
| 4 | AI assistant (Gemini) | Optional | `backend/.env` → `AI_ENABLED`, `GEMINI_API_KEY` | free tier / paid |
| 5 | Google AdSense | Optional | `VITE_ADS_*` | earns revenue |
| 6 | Ad-free licence keys | Optional | `backend/.env` → `PREMIUM_SECRET` | – |

## 1. Public site URL
- **Why:** canonical links, `sitemap.xml`, `robots.txt` and Open Graph previews need the real address.
- **Do:** create `frontend/.env.production` with `VITE_SITE_URL=https://your-domain.example` (no trailing slash) and rebuild (`npm run build` or `docker compose up -d --build`).
- **Test:** open `https://your-domain.example/sitemap.xml` — every `<loc>` must start with your domain.

## 2. Domain and HTTPS — see [DEPLOYMENT.md](DEPLOYMENT.md).

## 3. Contact e-mail
`VITE_CONTACT_EMAIL=you@example.com` in `frontend/.env.production`, rebuild. Empty hides it. Use a role address, not a personal one, because it is public.

## 4. AI assistant — see [API_SETUP.md](API_SETUP.md). Disable: `AI_ENABLED=false`.

## 5. Google AdSense — see [ADSENSE_SETUP.md](ADSENSE_SETUP.md). Disable: `VITE_ADS_ENABLED=false` and rebuild.

## 6. Ad-free licence keys (future premium tier)
- **Why:** lets you give or sell an ad-free experience without accounts. Keys are HMAC-signed and checked by `/api/v1/premium/verify`; visitors paste them under Settings.
- **Do:** `backend\.venv\Scripts\python -m app.cli new-secret` → put the value in `backend/.env` as `PREMIUM_SECRET=...`, restart. Issue a key: `python -m app.cli issue-key --label "Customer 123" --expires 2027-12-31` (run in `backend/`).
- **Test:** Settings shows an “Ad-free licence” card; paste the key → “Ad-free active”, ads disappear.
- **Note:** there is no payment integration; connecting a payment provider (e.g. Stripe Checkout + a webhook that calls `sign_key`) is future work. Keep `PREMIUM_SECRET` private — anyone with it can mint keys.

## Things you do NOT need
No database, no administrator account, no Firebase, no Track-N credentials, no e-mail server.
