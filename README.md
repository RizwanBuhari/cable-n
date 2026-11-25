# Cable-N — Cable Sizing & Engineering Intelligence

A public, account-free engineering website for sizing and verifying power cables. All numbers come from one deterministic Python engine — the original `cable_sizing_FINAL.py` program, used verbatim and proven equal to the original by automated tests.

| Mode | Page | What it does |
|---|---|---|
| 1 | `/calculators/single-feeder` | Design current, derating chain, voltage drop, short-circuit withstand, every single- and parallel-run option, diagrams |
| 2 | `/calculators/batch` | Cable schedule for up to 200 feeders, Excel import/template, per-row validation, background run with progress |
| 3 | `/calculators/current-rating` | Rating check of up to 3 duct banks / buried groups with mixed cables |
| 4 | `/calculators/advanced-mv-hv` | IEC 60287 / 60949: T1–T4, losses, mutual heating, electrical & sequence parameters, induced voltage, short-circuit, emergency ratings |

Plus: cable library, comparison / sensitivity / cost estimate, validation centre, engineering resources, local saved work (projects, revisions, templates), PDF / Excel / CSV / JSON exports, optional AI assistant, optional AdSense.

## Quick start (Windows)

```powershell
cd C:\Cable-N
.\scripts\setup.ps1     # venv + Python deps + npm deps + .env files
.\scripts\start.ps1     # API :8000, website :5173
```
Open http://localhost:5173 — no login, no database. API docs: http://localhost:8000/api/docs. Stop with `.\scripts\stop.ps1`.

## Production (one container)

```powershell
docker compose up -d --build     # http://localhost:8000 serves site + API
```
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for domain, HTTPS and SEO settings.

## Tests

```powershell
backend\.venv\Scripts\python -m pytest backend\tests -q     # 118 tests: parity with the original, validation, safety, API
cd frontend; npx playwright test                            # 9 browser tests (starts both servers)
```

## Documentation

| File | Contents |
|---|---|
| [docs/MANUAL_SETUP.md](docs/MANUAL_SETUP.md) | Everything you may need to configure yourself |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Structure, data flow, privacy model, security |
| [docs/ENGINE_MAPPING.md](docs/ENGINE_MAPPING.md) | Original Python functions → API → pages |
| [docs/VALIDATION.md](docs/VALIDATION.md) | Benchmark results, tolerances, parity testing |
| [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) | Approximations, failed benchmarks, open issues |
| [docs/API_SETUP.md](docs/API_SETUP.md) | Optional Gemini assistant |
| [docs/ADSENSE_SETUP.md](docs/ADSENSE_SETUP.md) | Optional Google AdSense, consent, ads.txt |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Hosting, HTTPS, domain, SEO |

> Results support — and never replace — the judgement of a qualified electrical engineer.
