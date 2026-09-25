"""Plotly Mesh3d helpers adapted from rescale-ai-examples / inference-templates."""

from __future__ import annotations

from typing import Any

PLOTLY_COLORSCALES = {
    "turbo": "Turbo",
    "viridis": "Viridis",
    "coolwarm": "RdBu_r",
    "plasma": "Plasma",
    "jet": "Jet",
    "rainbow": "Rainbow",
    "magma": "Magma",
}
COLORMAPS = list(PLOTLY_COLORSCALES)


def _stage(mesh: Any) -> str:
    try:
        return (
            f"{mesh.__class__.__name__}: "
            f"{int(getattr(mesh, 'n_points', 0)):,} pts, "
            f"{int(getattr(mesh, 'n_cells', 0)):,} cells"
        )
    except Exception as exc:
        return f"<unprintable: {exc}>"


def to_renderable_polydata(mesh: Any) -> tuple[Any | None, list[tuple[str, str]]]:
    debug: list[tuple[str, str]] = [("input", _stage(mesh))]
    try:
        import pyvista as pv  # noqa: F401
    except ImportError:
        return None, [("import", "pyvista is not installed")]

    candidate = mesh
    if candidate.__class__.__name__ == "MultiBlock":
        try:
            candidate = candidate.combine()
        except Exception as exc:
            debug.append(("combine", f"failed: {exc}"))
            return None, debug
        debug.append(("combine", _stage(candidate)))

    if hasattr(candidate, "extract_surface"):
        try:
            candidate = candidate.extract_surface(algorithm="dataset_surface")
        except TypeError:
            candidate = candidate.extract_surface()
        except Exception as exc:
            debug.append(("extract_surface", f"failed: {exc}"))
            return None, debug
        debug.append(("extract_surface", _stage(candidate)))

    if not getattr(candidate, "is_all_triangles", True):
        try:
            candidate = candidate.triangulate()
            debug.append(("triangulate", _stage(candidate)))
        except Exception as exc:
            debug.append(("triangulate", f"failed: {exc}"))
            return None, debug
    else:
        debug.append(("triangulate", "skipped (already all triangles)"))

    return candidate, debug


def weld_vertices(points, triangles, intensity, weld_tol: float):
    import numpy as np

    pts = np.asarray(points, dtype=np.float64)
    tris = np.asarray(triangles, dtype=np.int64)
    n_before = len(pts)
    if weld_tol <= 0 or n_before == 0:
        return pts, tris, intensity, n_before, n_before

    keys = np.floor(pts / weld_tol + 0.5).astype(np.int64)
    _, first_idx, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    new_pts = pts[first_idx]
    new_tris = inverse[tris]

    new_intensity = None
    if intensity is not None:
        intensity_arr = np.asarray(intensity, dtype=np.float64)
        sums = np.zeros(len(new_pts), dtype=np.float64)
        counts = np.zeros(len(new_pts), dtype=np.int64)
        np.add.at(sums, inverse, intensity_arr)
        np.add.at(counts, inverse, 1)
        new_intensity = sums / np.maximum(counts, 1)

    return new_pts, new_tris, new_intensity, n_before, len(new_pts)


def build_mesh3d_figure(
    mesh: Any,
    scalar_name: str | None,
    cmap: str,
    *,
    weld_factor: float = 1e-4,
    height: int = 560,
    deform_scale: float = 1.0,
    displacement_name: str | None = None,
):
    """Build a Plotly Mesh3d figure; optionally warp by a displacement vector field."""
    try:
        import numpy as np
        import plotly.graph_objects as go
    except ImportError:
        return None, [("import", "plotly / numpy not installed")]

    surface, debug = to_renderable_polydata(mesh)
    if surface is None:
        return None, debug

    points = np.ascontiguousarray(np.asarray(surface.points), dtype=np.float64)
    if points.size == 0:
        debug.append(("verify", "no points"))
        return None, debug

    if displacement_name and deform_scale != 0.0:
        disp = surface.point_data.get(displacement_name)
        if disp is not None:
            disp = np.asarray(disp, dtype=np.float64)
            if disp.ndim == 2 and disp.shape[1] >= 3:
                points = points + deform_scale * disp[:, :3]
                debug.append(
                    ("deform", f"{displacement_name} × {deform_scale:g}")
                )

    faces = np.asarray(surface.faces, dtype=np.int64)
    if faces.size == 0 or faces.size % 4 != 0:
        debug.append(("verify", f"faces.size={faces.size} (not triangular)"))
        return None, debug
    triangles = faces.reshape(-1, 4)[:, 1:]

    intensity = None
    if scalar_name:
        arr = surface.point_data.get(scalar_name)
        if arr is not None:
            arr = np.asarray(arr)
            if arr.ndim > 1:
                arr = np.linalg.norm(arr, axis=-1)
            intensity = np.ascontiguousarray(arr, dtype=np.float64)

    if weld_factor > 0:
        bbox_diag = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))
        weld_tol = bbox_diag * weld_factor
        if weld_tol > 0:
            points, triangles, intensity, n_before, n_after = weld_vertices(
                points, triangles, intensity, weld_tol
            )
            debug.append(
                (
                    "weld_vertices",
                    f"{n_before:,} → {n_after:,} pts (tol={weld_tol:.3g})",
                )
            )

    colorbar = None
    if intensity is not None:
        cb_min = float(np.nanmin(intensity))
        cb_max = float(np.nanmax(intensity))
        if cb_min == cb_max:
            cb_max = cb_min + 1.0
        ticks = np.linspace(cb_min, cb_max, 6)
        colorbar = dict(
            title=dict(text=scalar_name or "", font=dict(color="#222", size=12)),
            tickvals=ticks.tolist(),
            ticktext=[f"{v:.3g}" for v in ticks],
            tickfont=dict(color="#222", size=11),
            bgcolor="rgba(255,255,255,0.85)",
            thickness=16,
            len=0.85,
        )

    fig = go.Figure(
        data=[
            go.Mesh3d(
                x=points[:, 0],
                y=points[:, 1],
                z=points[:, 2],
                i=triangles[:, 0],
                j=triangles[:, 1],
                k=triangles[:, 2],
                intensity=intensity,
                intensitymode="vertex",
                colorscale=PLOTLY_COLORSCALES.get(cmap, "Viridis"),
                showscale=intensity is not None,
                colorbar=colorbar,
                flatshading=False,
                lighting=dict(ambient=0.7, diffuse=0.6, specular=0.0, roughness=1.0),
                hoverinfo="skip" if intensity is None else "text",
                name=scalar_name or "mesh",
            )
        ]
    )
    fig.update_layout(
        scene=dict(
            aspectmode="data",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            bgcolor="white",
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        paper_bgcolor="white",
        showlegend=False,
    )
    debug.append(("plotly", f"{len(triangles):,} triangles"))
    return fig, debug


def list_displacement_fields(mesh: Any) -> list[str]:
    """Return clean `displacement_t*` frames (skip residual / component dumps)."""
    import re

    names = list(getattr(mesh, "point_data", {}).keys())
    pat = re.compile(r"^displacement_t\d+\.\d+$")
    disp = [n for n in names if pat.match(n)]
    return sorted(disp, key=lambda n: float(n.split("displacement_t", 1)[1]))


def displacement_magnitude_name(field: str) -> str:
    """Return the same field; magnitude is computed in the plotter if vectorial."""
    return field
