# Handoff — McLaren P35 Streamlit crash-surrogate UI (Sep 25, 2026)

**Date:** 2026-09-25  
**Status:** Laptop **demo UI shipped** under `streamlit_app/`. Live GeoTransolver inference **not** wired yet (needs NVIDIA CUDA).  
**Related:** Platform UI inference broken for global-TS models — see [`handoff-2026-09-ui-walkthrough.md`](./handoff-2026-09-ui-walkthrough.md). Model plumbing: [`handoff-2026-08-geotransolver-global-ts.md`](./handoff-2026-08-geotransolver-global-ts.md).

---

## Original intention

Build a **customer-facing custom Streamlit interface** for McLaren’s side-pole crash surrogate so they can:

1. Twiddle the **~10 DOE design knobs** (binary on/off vs thickness / foam / TTF levels).
2. See **crash displacement** on the decimated mesh (time-scrubbable).
3. See the **28 global occupant-probe time series** the GeoTransolver head predicts (head/neck/ribs/pelvis/etc.).

Inspiration / scaffolding:

- `rescale-ai-examples/inference/gui_examples/streamlit_app`
- `rescale-ai-inference-templates` (Streamlit template + Rescale theme helpers)

**Target model:** `myCool_decimated_SidePoleCrash_GeoT` v0  
- Job **RqRMX**, 200 epochs, decimated ~20k pts  
- `global_dim: 10`, `global_output_dim: 28`, `geotransolver_time_conditional`  
- Storage (HPS): `…/models/myCool_decimated_SidePoleCrash_GeoT/versions/0/`

**Why a custom UI at all:** the stock AI Physics webapp path for this model can train/eval and show Global Outputs in Evaluation, but **UI inference for global-feature models was non-functional** (sliders not wired; missing `case_data.yml` / metadata). A Streamlit + `rescale-ai-client` (or local runner) front-end was the intended workaround for demos.

---

## What shipped (Sep 25)

| Piece | Path |
|-------|------|
| App | `streamlit_app/app.py` |
| Knob schema (binary vs select) | `streamlit_app/knobs.json` |
| Cached-eval loader | `streamlit_app/demo_store.py` |
| Plotly mesh helper | `streamlit_app/mesh_plot.py` |
| Demo artifacts | `streamlit_app/demo_data/` (17 `*_global_values.json` + `cases.csv`; VTPs gitignored — pull with script) |
| Pull script | `streamlit_app/pull_demo_data.sh` |
| Inference case YAML template | `case_data_inference.yml` |

**Laptop mode today:** nearest-match knobs → precomputed eval case → plot that case’s probes (+ VTP if present). **Not** a live forward pass.

**Knob classification (from train DOE `cases.csv`):**

- **Binary on/off (0/1):** `airbag_E22`, `brace_P16`, `bracket_cutt`, `rail_foam`, `seat_inb_foam`
- **DOE discrete levels:** `airbag_z_up_mm` {0,30}, `cavity_foam_gl` {0,60,140}, `door_inner_mm` {1.1,1.2,1.3}, `door_outer_mm` {1.1,1.2}, `ttf_ms` {9,12}

---

## What blocked live local inference

- GeoTransolver needs **CUDA**. Apple Silicon Mac has Metal only.
- Interactive WS `udeprod_yJnke` was **Kyanite** (`RESCALE_GPUS_PER_NODE=0`) — same storage as the model, no GPU.
- Grossular queue was unavailable for ~30+ min when we tried to stand up a GPU box.

**Next (when GPU exists):** point sidebar “Live inference” at a CUDA `rescale-ai` / local-inference endpoint (tile ≥ global-TS plumbing, e.g. 2.1.10+), pass the 10 knobs + a decimated base `case.vtp` / `case_data.yml`, render returned mesh + `*_global_values.json`-shaped probes.

---

## How to run

```bash
cd streamlit_app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# optional: bash pull_demo_data.sh udeprod_yJnke@<host>
streamlit run app.py
```

---

## Do not confuse

| Artifact | Notes |
|----------|--------|
| `myCool_decimated_SidePoleCrash_GeoT` | **Use this** — decimated, 200 ep, joint nodal + 28 probes |
| `myCool_SidePoleCrash_GeoTransolver_model` | Earlier / failed license attempt |
| Old 39-channel holdout docs | Poisoned labels — ignore for probe accuracy |
| Platform Evaluation “Global Outputs” | Works on eval JSON; **Inference tab** was the broken path |
