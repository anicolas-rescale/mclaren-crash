"""McLaren P35 side-pole crash surrogate — Streamlit demo UI.

Pattern adapted from:
  - rescale-ai-examples/inference/gui_examples/streamlit_app
  - rescale-ai-inference-templates/templates/streamlit

Laptop mode uses cached eval artifacts (no CUDA). When a GPU inference
endpoint is available later, flip sidebar mode to "Live inference".

Launch:
    cd mclaren-crash-pole/streamlit_app
    python -m pip install -r requirements.txt
    streamlit run app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from demo_store import (
    KNOB_KEYS,
    PROBE_CHANNELS,
    demo_data_ready,
    knob_distance,
    list_all_eval_cases,
    load_cases,
    load_global_values,
    load_knobs_config,
    probe_series,
    vtp_path_for,
)
from mesh_plot import COLORMAPS, build_mesh3d_figure, list_displacement_fields

APP_DIR = Path(__file__).resolve().parent
ASSETS = APP_DIR / "assets"


def _inject_theme() -> None:
    css_path = ASSETS / "rescale.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.2rem; max-width: 1400px; }
        div[data-testid="stMetricValue"] { font-size: 1.15rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_knob_controls() -> dict[str, float]:
    cfg = load_knobs_config()
    values: dict[str, float] = {}
    st.sidebar.subheader("Design knobs")
    st.sidebar.caption(
        "Binary = on/off (0/1). Others use DOE discrete levels from the training set."
    )

    binary_keys = [k for k in KNOB_KEYS if cfg[k]["kind"] == "binary"]
    select_keys = [k for k in KNOB_KEYS if cfg[k]["kind"] != "binary"]

    st.sidebar.markdown("**On / off**")
    for key in binary_keys:
        meta = cfg[key]
        default_on = float(meta["default"]) == float(meta["on"])
        on = st.sidebar.toggle(
            meta["label"],
            value=default_on,
            help=meta.get("help"),
            key=f"tog_{key}",
        )
        values[key] = float(meta["on"] if on else meta["off"])

    st.sidebar.markdown("**Continuous / DOE levels**")
    for key in select_keys:
        meta = cfg[key]
        options = [float(x) for x in meta["options"]]
        unit = meta.get("unit") or ""
        label = f"{meta['label']}" + (f" ({unit})" if unit else "")
        default = float(meta["default"])
        try:
            idx = options.index(default)
        except ValueError:
            idx = 0
        choice = st.sidebar.select_slider(
            label,
            options=options,
            value=options[idx],
            help=meta.get("help"),
            key=f"sel_{key}",
            format_func=lambda v, u=unit: f"{v:g}{(' ' + u) if u else ''}",
        )
        values[key] = float(choice)

    return values


def _build_probe_figure(
    global_values: dict,
    channels: list[str],
    *,
    show_actual: bool,
):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    n = len(channels)
    if n == 0:
        return None
    cols = 2 if n > 1 else 1
    rows = (n + cols - 1) // cols
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=channels,
        vertical_spacing=0.06,
        horizontal_spacing=0.08,
    )
    for i, ch in enumerate(channels):
        r = i // cols + 1
        c = i % cols + 1
        time, pred, actual = probe_series(global_values, ch)
        if not time or not pred:
            continue
        fig.add_trace(
            go.Scatter(
                x=time,
                y=pred,
                mode="lines",
                name=f"{ch} pred",
                line=dict(color="#2460ff", width=2),
                showlegend=(i == 0),
                legendgroup="pred",
            ),
            row=r,
            col=c,
        )
        if show_actual and actual is not None:
            fig.add_trace(
                go.Scatter(
                    x=time,
                    y=actual,
                    mode="lines",
                    name=f"{ch} actual",
                    line=dict(color="#c34475", width=1.5, dash="dash"),
                    showlegend=(i == 0),
                    legendgroup="actual",
                ),
                row=r,
                col=c,
            )
    fig.update_layout(
        height=max(280, 220 * rows),
        margin=dict(l=40, r=20, t=40, b=30),
        paper_bgcolor="white",
        plot_bgcolor="#f4f8fa",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.update_xaxes(title_text="time (s)", gridcolor="#cddce4")
    fig.update_yaxes(gridcolor="#cddce4")
    return fig


def _render_displacement_section(case_id: str) -> None:
    st.subheader("Crash displacements")
    vtp = vtp_path_for(case_id)
    if vtp is None:
        st.info(
            f"No local mesh for `{case_id}`. "
            "Probe plots below still work. Pull more `.vtp` files into "
            "`streamlit_app/demo_data/evaluation/` for 3D."
        )
        return

    try:
        import pyvista as pv
    except ImportError:
        st.error("Install `pyvista` to view displacement meshes.")
        return

    mesh = pv.read(str(vtp))
    fields = list_displacement_fields(mesh)
    if not fields:
        st.warning("No `displacement_t*` arrays found on this mesh.")
        return

    # Prefer mid / late crash frame as default
    default_field = fields[min(len(fields) - 1, len(fields) // 2)]
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    with c1:
        field = st.selectbox(
            "Displacement frame",
            fields,
            index=fields.index(default_field),
        )
    with c2:
        cmap = st.selectbox("Colormap", COLORMAPS, index=0)
    with c3:
        deform = st.slider("Deform scale", 0.0, 5.0, 1.0, 0.1)
    with c4:
        color_by_mag = st.checkbox("Color by |u|", value=True)

    scalar = field if color_by_mag else None
    fig, debug = build_mesh3d_figure(
        mesh,
        scalar,
        cmap,
        deform_scale=deform,
        displacement_name=field,
    )
    if fig is None:
        st.error("Could not build mesh figure.")
        with st.expander("Diagnostics"):
            st.write(debug)
        return
    st.plotly_chart(fig, width="stretch")
    st.caption(
        f"Mesh `{vtp.name}` · field `{field}` · deform×{deform:g} · "
        f"{mesh.n_points:,} points"
    )


def _render_probe_section(case_id: str) -> None:
    st.subheader("Global time-series probes (28 channels)")
    try:
        gv = load_global_values(case_id)
    except FileNotFoundError:
        st.warning(f"No probe JSON for `{case_id}`.")
        return

    show_actual = st.checkbox(
        "Overlay ground-truth (eval cases)",
        value=True,
        help="Dashed = measured; solid blue = model prediction.",
    )
    groups = {
        "Head / neck": [c for c in PROBE_CHANNELS if c.startswith(("head_", "neck_"))],
        "Thorax (ribs / T1 / T12)": [
            c
            for c in PROBE_CHANNELS
            if "rib" in c or c.startswith(("t1_", "t12_"))
        ],
        "Pelvis / pubic / shoulder": [
            c
            for c in PROBE_CHANNELS
            if c.startswith(("pelvis_", "pubic_", "shoulder_"))
        ],
        "All 28": PROBE_CHANNELS,
    }
    group_name = st.selectbox("Probe group", list(groups.keys()), index=0)
    selected = groups[group_name]

    if group_name == "All 28":
        pick = st.multiselect(
            "Channels",
            PROBE_CHANNELS,
            default=PROBE_CHANNELS[:6],
        )
        channels = pick or PROBE_CHANNELS[:6]
    else:
        channels = selected

    fig = _build_probe_figure(gv, channels, show_actual=show_actual)
    if fig is None:
        st.warning("No probe series to plot.")
        return
    st.plotly_chart(fig, width="stretch")

    with st.expander("Raw JSON keys"):
        st.write(sorted(gv.keys()))


def _enrich_cases_with_holdouts() -> list[dict]:
    """Merge train cases.csv with any eval JSONs (incl. holdouts)."""
    by_id = {c["case_id"]: c for c in load_cases()}
    for case_id in list_all_eval_cases():
        if case_id in by_id:
            continue
        try:
            gv = load_global_values(case_id)
        except FileNotFoundError:
            continue
        knobs = {k: float(gv[k]) for k in KNOB_KEYS if k in gv}
        if len(knobs) != len(KNOB_KEYS):
            continue
        by_id[case_id] = {
            "case_id": case_id,
            "case_path": f"(holdout) {case_id}",
            "knobs": knobs,
            "global_json": APP_DIR
            / "demo_data"
            / "evaluation"
            / f"prediction_{case_id}_global_values.json",
            "vtp": APP_DIR / "demo_data" / "evaluation" / f"prediction_{case_id}.vtp",
        }
    return list(by_id.values())


def main() -> None:
    st.set_page_config(
        page_title="McLaren P35 Crash Surrogate",
        page_icon="🏎️",
        layout="wide",
    )
    _inject_theme()

    st.title("McLaren P35 — side-pole crash surrogate")
    st.caption(
        "GeoTransolver transient · `myCool_decimated_SidePoleCrash_GeoT` · "
        "nodal displacement + 28 global probe channels"
    )

    with st.sidebar:
        st.header("Mode")
        mode = st.radio(
            "Prediction source",
            ["Cached eval (laptop demo)", "Pick eval case", "Live inference (GPU)"],
            index=0,
            help=(
                "Laptop demo matches knobs to the nearest precomputed eval case. "
                "Live inference needs a CUDA endpoint — not available on Apple Silicon."
            ),
        )
        st.divider()

    knobs = _render_knob_controls()

    ready, ready_msg = demo_data_ready()
    st.sidebar.caption(ready_msg)

    if mode == "Live inference (GPU)":
        st.warning(
            "Live GeoTransolver inference needs NVIDIA CUDA. "
            "Your Mac (Apple Silicon) and the current Kyanite workstation cannot run it. "
            "Use **Cached eval** until a Grossular (or similar) endpoint is up."
        )
        endpoint = st.text_input("Inference endpoint", "http://127.0.0.1:65432")
        st.code(
            "# When a GPU runner is available:\n"
            "from rescale_ai_client import InferenceClient\n"
            f"client = InferenceClient.connect(base_url={endpoint!r})\n"
            "# then run_inference(...) with these knobs:\n"
            + json.dumps(knobs, indent=2),
            language="python",
        )
        st.stop()

    if not ready and mode != "Pick eval case":
        st.error(ready_msg)
        st.info(
            "From your laptop, pull demo artifacts:\n\n"
            "```bash\n"
            "cd mclaren-crash-pole/streamlit_app\n"
            "bash pull_demo_data.sh udeprod_yJnke@18.201.17.179\n"
            "```"
        )
        st.stop()

    if mode == "Pick eval case":
        case_ids = list_all_eval_cases()
        if not case_ids:
            st.error("No eval JSONs found under demo_data/evaluation/.")
            st.stop()
        case_id = st.selectbox("Eval case", case_ids)
        exact = True
    else:
        # Nearest-neighbor among train + holdouts that have probe JSON
        catalog = _enrich_cases_with_holdouts()
        if not catalog:
            st.error("No cases available.")
            st.stop()
        ranked = sorted(catalog, key=lambda c: knob_distance(knobs, c["knobs"]))
        best = ranked[0]
        case_id = best["case_id"]
        distance = knob_distance(knobs, best["knobs"])
        exact = distance < 1e-9

    m1, m2, m3 = st.columns(3)
    m1.metric("Case", case_id)
    m2.metric("Match", "exact" if exact else "nearest")
    m3.metric("Model", "GeoT · 200 ep · decimated")

    with st.expander("Active knobs", expanded=False):
        st.json(knobs)

    _render_displacement_section(case_id)
    st.divider()
    _render_probe_section(case_id)


if __name__ == "__main__":
    main()
