# Engine mapping — original program → Cable-N

`reference/original_engine/cable_sizing_FINAL.py` (SHA-256 `fb3abae2…0492157`, identical to the file in Downloads) is copied **verbatim** into `backend/app/engine/legacy_engine.py` by `build_legacy.py`, with two I/O-only patches (removing a copy of PDFs to `/mnt/user-data/outputs` in `generate_batch_pdf` and `generate_mode4_pdf`). `tests/test_engine_integrity.py` proves every other function and constant is AST-identical.

Terminal I/O is handled by `app/engine/runtime.py`: `input()` answered from a script (an unexpected prompt raises instead of blocking), stdout captured as engine messages, FPDF output redirected to a temporary folder, plus a cursor-default shim for fpdf2 ≥ 2.5.2 (see KNOWN_LIMITATIONS).

| Original function(s) | Adapter | API | Page |
|---|---|---|---|
| `get_user_input`, `select_arrangement`, `interactive_main` (dialogue) | `mode1.to_legacy_inputs`, `arrangement_options`, `run_single_feeder` | `POST /calculations/single-feeder`, `/single-feeder/arrangements` | Single feeder |
| `calculate_current`, `calculate_derating_factors`, `calculate_voltage_drop`, `calculate_short_circuit`, `sc_adequacy`, `build_solution`, `find_single_run_solutions`, `find_multi_run_solutions`, `find_all_run_options`, `pick_recommended`, `governing_constraint`, `summarize_exclusions`, `matrix_cell`, `circuit_description`, `installation_description`, `chain_string` | called unchanged by `mode1` / `mode2` | as above | Single feeder, Batch |
| `generate_pdf_report` (+ `draw_installation_diagram`, `pdf_*` helpers) | `mode1.generate_pdf` | `POST /outputs/report.pdf` (detailed) | PDF report |
| `collect_common_inputs`, `collect_feeders`, `batch_main` (dialogue) | `mode2.common_to_legacy`, `feeder_to_legacy`, `validate_feeder`, `run_batch` | `POST /calculations/batch`, `/batch/jobs`, `/batch/import`, `/batch/template.xlsx` | Batch |
| `size_feeder`, `generate_batch_pdf`, `print_batch_schedule` | called unchanged / PDF via `mode2.generate_pdf` | `/outputs/report.pdf` | Batch |
| `collect_multi_bank_inputs`, `rating_main` (dialogue) | `mode3.build_site` | `POST /calculations/current-rating` | Current rating |
| `cfg_table_and_method`, `spacing_key_from_pitch`, `rate_site`, `generate_rating_pdf`, `draw_site_diagram` | unchanged | as above, `/outputs/report.pdf` | Current rating |
| `choose_standard`, `STANDARDS` | `mode4.prepare_arrangement` | `/advanced-mvhv/presets` | Advanced |
| `define_cable` (dialogue) | `mode4.build_cable` (non-interactive transcription, parity-tested) | `/advanced-mvhv/cable-preview` | Advanced → cable editor |
| `mode4_full_report` (dialogue), `collect_duct_banks`, `place_cables_in_banks`, `_expand_circuit` | `mode4.prepare_arrangement`, `_bank_coords`, `run_full_report` | `POST /calculations/advanced-mvhv` | Advanced |
| `solve_arrangement_xy`, `cable_thermal`, `iec_*` (R, λ1, λ2, T1–T4, rating, air rating, Wd, G), `soil_rho_*`, `_losses_at_temp`, `axial_spacing`, `core_lay_factor` | unchanged | as above | Advanced: ratings, thermal, losses |
| `calc_electrical`, `calc_sequence`, `calc_induced` | unchanged | as above | Advanced: electrical, sequence & induced |
| `suite_adiabatic` (IEC 60949) | unchanged | as above | Advanced: short circuit |
| `emergency_rating`, `_minus_Ei`, `_Ei_series` (IEC 60853-2) | unchanged | as above (buried + emergency) | Advanced: emergency |
| `_sensitivity_tables` | data reproduced by `mode4.sensitivity` with the same calls and grids | `/advanced-mvhv/sensitivity` | Advanced: sensitivity |
| `_draw_isotherms` | field reproduced by `mode4.isotherm_field` | `/advanced-mvhv/isotherms` | Advanced: layout heat map |
| `generate_mode4_pdf`, `_draw_arrangement`, `_draw_bank_layout` | unchanged via `mode4.generate_pdf` | `/outputs/report.pdf` | PDF report |
| `mode4_validate`, `suite_validate`, `emergency_validate`, `mode4_cymcap_validate`, `cymcap_ductbank_validate`, `cymcap_3core_validate`, `volta_validate`, `transco_validate`, `soil_validate`, `ground3c_validate`, `ductbank_validate`, `esf_validate` | `validation/runner.py` (runs unchanged, dedicated output parser each) | `/validation/*` | Validation centre |
| `base_current_tables`, `calculate_voltage_drop` R/X tables, `IEC_R0_20C` | `services/library.py` | `GET /cable-library` | Cable library |
| `mode4_rate_defined` | **not exposed** — dead code in the original (never called) | – | – |
| `main`, `mode4_main`, `get_valid_float`, `get_optional_float`, `ask_phase`, `print_*` | replaced by typed forms and structured JSON | – | – |

Cable-N additions that are **not** in the original (and use only engine outputs): sensitivity sweeps (re-running the engine per point), cost estimate (user prices × lengths; losses with the engine's R table), comparison, local saved work, Cable-N cover/summary pages and traceability stamp in reports, Excel/CSV/JSON exports.
