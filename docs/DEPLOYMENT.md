# Deployment

Cable-N is one stateless container: FastAPI serves `/api/v1/*` and the pre-built website (with per-route pre-rendered HTML for SEO). No database, no volumes.

## Docker (recommended)
```powershell
copy backend\.env.example backend\.env      # set APP_ENV=production, optional AI / PREMIUM keys
# public build settings: create .env in the project root (read by docker compose)
#   VITE_SITE_URL=https://your-domain.example
#   VITE_CONTACT_EMAIL=...   VITE_ADS_ENABLED=...   (see ADSENSE_SETUP.md)
docker compose up -d --build
```
Health: `http://SERVER:8000/api/v1/health`.

## Domain and HTTPS
1. Buy a domain; create an `A` record pointing to your server's public IP.
2. Put a reverse proxy with automatic TLS in front, e.g. Caddy (`Caddyfile`):
   ```
   your-domain.example {
       reverse_proxy 127.0.0.1:8000
   }
   ```
3. In `backend/.env` set `TRUST_PROXY_HEADERS=true` (so rate limits use the real client IP) and keep port 8000 closed to the internet (firewall).
4. Rebuild with `VITE_SITE_URL=https://your-domain.example`.

## Without Docker
```powershell
cd frontend; npm ci; npm run build        # creates frontend\dist (+ sitemap, robots, ads.txt)
cd ..\backend; .venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## SEO checklist
- Each tool has its own URL and title/description (`frontend/src/seo/routes.js`); `postbuild.mjs` writes `dist/<route>/index.html` with those tags, canonical URL and Open Graph image (`/brand/og-image.png`).
- Submit `https://your-domain.example/sitemap.xml` in Google Search Console (verify via DNS TXT record).
- `robots.txt` disallows `/api/`.

## Scaling notes
Rate limits and job progress live in process memory. With several workers/containers each enforces its own limits; for strict global limits put the site behind a proxy/CDN rate limit (e.g. Cloudflare) as well.

## Updating the engine
Replace `reference/original_engine/cable_sizing_FINAL.py`, run `python -m app.engine.build_legacy`, update `ORIGINAL_SHA256`/`ENGINE_VERSION` in `app/engine/runtime.py`, run the full test suite, update VALIDATION.md.
