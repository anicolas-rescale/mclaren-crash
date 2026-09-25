# McLaren P35 crash surrogate — Streamlit UI

Custom Streamlit app for `myCool_decimated_SidePoleCrash_GeoT` (GeoTransolver
transient, decimated mesh, 200 epochs): **10 design knobs**, **crash
displacement** mesh view, and **28 global probe** time-series plots.

Built from the patterns in:

- `rescale-ai-examples/inference/gui_examples/streamlit_app`
- `rescale-ai-inference-templates/templates/streamlit`

## Knob types (from training DOE)

| Knob | UI | DOE values |
|------|----|------------|
| `airbag_E22` | on/off | 0 / 1 |
| `brace_P16` | on/off | 0 / 1 |
| `bracket_cutt` | on/off | 0 / 1 |
| `rail_foam` | on/off | 0 / 1 |
| `seat_inb_foam` | on/off | 0 / 1 |
| `airbag_z_up_mm` | select | 0, 30 mm |
| `cavity_foam_gl` | select | 0, 60, 140 |
| `door_inner_mm` | select | 1.1, 1.2, 1.3 mm |
| `door_outer_mm` | select | 1.1, 1.2 mm |
| `ttf_ms` | select | 9, 12 ms |

## Laptop demo mode (no GPU)

Until a CUDA inference endpoint is available, the app **nearest-matches** your
knobs to a precomputed eval case and plots that case’s displacement VTP + probe
JSON. This is not a live forward pass.

```bash
cd streamlit_app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Refresh cached artifacts from a workstation:

```bash
bash pull_demo_data.sh udeprod_yJnke@18.201.17.179
```

## Live inference

Sidebar → **Live inference (GPU)** shows the endpoint stub. Wire
`rescale-ai-client` once a Grossular (or similar) runner is up — Apple Silicon
cannot run GeoTransolver.
