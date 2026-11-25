# Architecture

```
Browser (React 19 + Vite, public, no login)
  ├─ pages / calculators / results / diagrams (SVG)
  ├─ IndexedDB: saved calculations (+revision history), projects, templates, custom cables
  └─ localStorage: drafts (autosave), preferences, accent, consent, licence
        │  JSON inputs only (never results)
        ▼
FastAPI  /api/v1  (stateless, no database)
  ├─ core/protect.py   per-IP rate limits, daily AI quotas, bounded engine pool + timeouts
  ├─ api/calc.py       4 modes, helpers, sweeps, cost, batch jobs
  ├─ api/outputs.py    PDF / Excel / CSV — recomputed from inputs, temp dir deleted
  ├─ api/reference.py  validation centre, cable library, datasheet extraction, health, licence
  ├─ api/assistant.py  optional Gemini (recomputes shared context)
  └─ engine/  legacy_engine.py (verbatim original) + runtime.py + mode1-4 adapters
```

## Repository
```
backend/   app/{api,core,engine,reports,schemas,services,validation}, tests/, requirements*.txt, .env.example
frontend/  src/{components,calculators,results,diagrams,pages,lib,seo,styles}, public/brand, scripts/, e2e/
reference/original_engine/  read-only copy of the original program
scripts/   setup.ps1, start.ps1, stop.ps1, brand/build_brand.py
docs/      this folder
Dockerfile, docker-compose.yml
```

## Key decisions
- **Engine authority**: no formula is reimplemented in JavaScript. The browser renders engine output; exports/reports always recompute server-side from inputs.
- **Public & private by default**: no accounts; inputs are processed and forgotten; saved work stays on the device; export/import JSON for backup and transfer.
- **Traceability**: every report/export carries engine version + SHA-256 of the validated inputs; same inputs → same fingerprint.
- **Honest status**: results show “executed”, numerical checks PASS/FAIL, warnings, and a verification notice; reports state “NOT REVIEWED”. No signatures or approvals.
- **Design system**: Track-N tokens, components and animations (logo sheen, staggered reveals, page transitions, reduced-motion support); status colours fixed and independent of the accent.
- **Brand**: independent Cable-N identity — trefoil cable cross-section mark + Montserrat ExtraBold wordmark (outlined SVG); generator `scripts/brand/build_brand.py`, PNGs via `frontend/scripts/render-brand.mjs`.
- **SEO**: dedicated URL per tool, per-route pre-rendered `<head>`, sitemap.xml, robots.txt, Open Graph image, self-hosted fonts (no third-party font requests).

## Security
Pydantic validation with original prompt bounds (+ finite-number checks), request body 512 KB / upload 8 MB limits, file-type sniffing, per-IP rate limits (calc 60/min, reports 6/min, validation 4/min, AI 3/min + 20/day + global cap), bounded concurrency and timeouts, CORS limited to configured origins without credentials, security headers (nosniff, frame, referrer, permissions, HSTS in production), generic 500 errors in production, path-traversal-safe static serving, secrets only in `backend/.env`, non-root read-only container.
