# Known limitations

## Engineering approximations inherited from the original engine (preserved, disclosed in results)
- **PVC**: base tables are 90 °C XLPE; PVC uses θmax 70 °C in Ca plus a ×0.90 factor — approximate; verify against PVC tables.
- **Nearest-value lookups** for soil/duct resistivity (0.7–3.0), depth (0.5–3.0 m), voltage-drop R/X tables and sizes; no interpolation or extrapolation. Out-of-range inputs are flagged.
- **Ca for ambient ≥ θmax**: the original substitutes 0.01. Cable-N blocks such inputs instead of returning that value.
- **Batch mode** always uses XLPE ratings and equal fault sharing (as the original asks neither question).
- **Mode 3** is a table method: each 2-D bank is a horizontal group; vertical heating via the depth factor only; mixed sizes share one Cg; envelope resistivity chosen, two-region soil not modelled; >12 circuits capped at the 12-circuit factor.
- **Mode 4**: multi-bank results unvalidated against CYMCAP (labelled); screened 3-core λ2 ≈55 % low vs CIGRE-guidance studies; belted 3-core λ1 ×0.1 approximation; Fig. 6 G fit validated only for t/d 0.045–0.06; solar term not calibrated; h for stacked groups may be optimistic; capacitance of screened 3-core ≈10 % low; load-factor sensitivity uses a simplified μ scaling.
- **Validation**: 4 cases outside tolerance and 1 legacy case with known gaps — see VALIDATION.md. Benchmarks are source-provided, not independently verified.
- `mode4_rate_defined()` in the original is dead code and is not exposed.

## Cable-N implementation notes
- **fpdf2 cursor behaviour**: the original's report code assumes the classic PyFPDF `multi_cell` (cursor to left margin). With fpdf2 ≥ 2.5.2 it raised “Not enough horizontal space”. Fixed by a default-only shim in the FPDF subclass, not by editing the original.
- The original's Mode 4 report diagram can overlap a cable label with its caption (cosmetic, original drawing).
- **Mode 4 overlap check** is a Cable-N addition: cables (or ducts) closer than their diameters are rejected.
- Engine calls are serialised by one lock (module-global I/O redirection). Fine for millisecond calculations; heavy concurrent load queues. Python threads cannot be killed: the 20 s timeout stops the client waiting, while input caps (200 feeders, 15 sweep points, 24 circuits/duct positions) bound the actual work.
- Rate limits, AI daily counters and job progress are in-process memory; multiple workers enforce limits separately and restarts reset them.
- Saved work is browser-local (IndexedDB): not synchronised, lost if site data is cleared, ~1.5 MB result trimming for very large batches.
- Datasheet extraction is regex-based on PDF text; scanned PDFs yield nothing; every value must be verified. AI-assisted extraction is not implemented.
- The premium tier has licence-key verification but no payment integration.
- Docker image: Dockerfile and compose were written but could not be built on the development machine because Docker Desktop was not running; the same production path (built site served by FastAPI) was tested without Docker.
- Diagrams: Mode 1 drawings are schematic (labelled); Mode 3/4 are to scale. The drag editor moves buried Mode 4 circuits horizontally only; other edits are made in the forms.
