# Validation and testing

## 1. Parity with the original program (`backend/tests/test_parity_original.py`)
The untouched original is loaded as its own module and driven through its **terminal dialogues** with scripted answers (an unexpected prompt fails the test). Its internal results are recorded and compared with the website adapters. Tolerance: exact (relative 1e-12, only to absorb re-parsed text answers).

| Mode | Cases | Compared |
|---|---|---|
| 1 | 6 input sets × every rated arrangement (Cu/Al, 1C/3C, buried/duct/air, A/kW/kVA/MW/MVA, single/three phase, PVC, equal/full fault sharing) | parsed inputs, Ib, every single-run solution, parallel options, printed recommendation lines |
| 2 | 2 common blocks × 5 feeders | every `size_feeder` row: Ib, recommendation, candidates, spacing variants, governing, exclusions |
| 3 | 3 sites (1–3 banks, backfill choices, overrides) | site dict and every position rating |
| 4 | 5 arrangements (buried + emergency, backfill flat-spaced, 2-bank mixed-load duct with Neher/direct ρ, air with trough + solar, layered soil 3-core) | cable definitions, every placed cable (T1–T4, R, λ1, λ2, Wd, I, θ), electrical, short-circuit, emergency |

Result: **16/16 pass.** One subtlety found and reproduced: the batch dialogue stores each feeder's VD limit as `(common×100)/100`.

## 2. Original benchmark routines (Validation centre)
Run unchanged; a dedicated parser per routine extracts rows (a generic regex parser was rejected after it mis-paired numbers). Headline rows = what the routine presents as its result; intermediate rows judged separately.

Tolerances: routine's own where stated (mode4 0.5 %, emergency ≈5 %, soil blend 25 %); otherwise Cable-N acceptance 5 % on ratings / 5 K on temperature (1 % for the workbook suite). These are inter-tool comparison bands, not compliance limits.

| Case | Status | Notes |
|---|---|---|
| mode4_validate | PASS | worst 0.05 % |
| suite_validate | PASS | 9/9 exact |
| emergency_validate | OUTSIDE_TOLERANCE | θ at 5 h: +5.3 % (others ≤ 4.2 %); Ta constant +5.5 % |
| mode4_cymcap_validate | PASS | 0.00 % |
| cymcap_ductbank_validate | PASS | −2.5 %; λ2 +1.2 % |
| cymcap_3core_validate | KNOWN_GAPS | legacy check; routine itself flags T1/T2 GAP (superseded by transco) |
| volta_validate | OUTSIDE_TOLERANCE | Neher model up to +21 K, layer model up to +12 K; CYMCAP-ρ route within 4.5 K |
| transco_validate | OUTSIDE_TOLERANCE | strict-IEC Neher ρ +8.3 %; with CYMCAP ρ −0.2…+0.8 %; λ2 −55 % |
| soil_validate | PASS | blend worst 22.9 %; Neher/radial up to 43.5 % (intermediate) |
| ground3c_validate | PASS | ampacity −1.5 %, θ within 0.05 K; C −10 % (documented) |
| ductbank_validate | OUTSIDE_TOLERANCE | 4 circuits: Neher +5.2 %, layer +6.1 %; CYMCAP ρ +1.9 % |
| esf_validate | PASS | ratings ≤ 1.4 %; 3-core λ2 −53 %, T1 +22.6 % strict-IEC (intermediate) |

Benchmarks are values quoted in the source program; **not independently verified**. Passing is not certification or CYMCAP equivalence. `tests/test_validation_cases.py` pins these statuses so any engine change forces this table to be updated.

## 3. Other automated tests
- `test_engine_integrity.py` — reference hash, regenerated module, AST identity except the 2 patches.
- `test_input_safety.py` (38) — negative/zero/NaN/∞ values, PF 0 with kW, ambient ≥ θmax, unit conversions kW/kVA/MW/MVA × 1/3-phase, % vs fraction, disclosure of PVC / table-range / fault-sharing assumptions, Mode 3/4 rejections, overlap.
- `test_api_public.py` (40) — every mode without login, no account endpoints, 422 shapes, body-size limit, batch cap, rate limit, PDF/Excel/CSV for all modes (no “Elsewedy”, “NOT REVIEWED” stamp, input hash), temp files removed, batch job progress, Excel import errors, sweeps, cost, library, validation job, datasheet rejection, assistant disabled, licence keys, path traversal.
- Frontend `e2e/site.spec.js` (Playwright, 9) — all pages render without console errors with own titles; all four calculators run; save → outdated flag → reopen saved; PDF + Excel downloads; validation run; mobile menu; accent changes brand but not status colours.

Run: `backend\.venv\Scripts\python -m pytest backend\tests -q` (118 passed) and `cd frontend; npx playwright test` (9 passed).
