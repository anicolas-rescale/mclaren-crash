# McLaren probe → global time-series schema

**Frozen:** 2026-08-12  
**Sources:** `automation-ai-extractor/.../probe_map.json`, `scorecard_field_map.json`  
**FEA contract:** `case_data.yml` → top-level `timeseries:` dict of float lists length `T` (same as FEA `outvar_ts_keys`)

## Instruments (12)

| Probe key | Role | Global scalar keys emitted |
|-----------|------|----------------------------|
| `head` | acceleration | `head_acceleration_{x,y,z}` |
| `t1` | acceleration | `t1_acceleration_{x,y,z}` |
| `t12` | acceleration | `t12_acceleration_{x,y,z}` |
| `pelvis` | acceleration | `pelvis_acceleration_{x,y,z}` |
| `upper_rib` | rib_defl | `upper_rib_defl`, `upper_rib_viscous_criterion` |
| `middle_rib` | rib_defl | `middle_rib_defl`, `middle_rib_viscous_criterion` |
| `lower_rib` | rib_defl | `lower_rib_defl`, `lower_rib_viscous_criterion` |
| `neck_upper` | force_moment | `neck_upper_force_{x,y,z}`, `neck_upper_moment_{x,y,z}` |
| `pubic` | force_moment | `pubic_force_{x,y,z}` |
| `shoulder_left` | force_moment | `shoulder_left_force_{x,y,z}` |
| `backplate` | force_moment | `backplate_force_{x,y,z}`, `backplate_moment_{x,y,z}` |
| `t12_loadcell` | force_moment | `t12_loadcell_force_{x,y,z}`, `t12_loadcell_moment_{x,y,z}` |

Missing PSA axes are omitted (not zero-filled) so `G_out` can be &lt; max. Max component set ≈ **42** (39 axes/defl + 3 rib VC) when every file exists; `*_resultant*` PSA channels are **not** extracted (derivable from xyz). Typical `HFuKPb`-class jobs emit **~40** (missing `t12_loadcell` Fz + Mz).

Optional documentation key (not a train target):

```yaml
timeseries:
  times: [0.0, 0.00199989, ...]   # mesh displacement frame times
```

## Example fragment

```yaml
door_inner_mm: 1.2
ttf_ms: 12.0
# ... other DOE knobs ...

timeseries:
  times: [0.0, 0.00199989, 0.00399978]
  head_acceleration_x: [0.0, 0.01, 0.02]
  head_acceleration_y: [0.0, -1.2, -2.0]
  head_acceleration_z: [0.0, 0.3, 0.4]
  upper_rib_defl: [0.0, 1.1, 2.3]
  pubic_force_y: [0.0, 0.5, 1.2]
```

## Train variable flags (after convert)

| Variable | Kind | Type |
|----------|------|------|
| DOE knobs (`door_inner_mm`, …) | global | **input** |
| `displacement_t*` | node | **output** |
| Probe bases above (as `name_t{time}` once platform expands, or as timeseries keys) | global | **output** |
| Sparse VTP `acceleration_t*` / `force_t*` / `moment_t*` / `rib_defl_t*` | node | **disabled** (do not train) |

Platform Transient today only understands node `_t*` outputs; Phase 2 teaches it global TS outputs. Until then, converted YAML is validated by `scripts/verify_probe_globals.py`.

## Alignment rule

`len(timeseries[<key>]) == T` where `T` = number of `displacement_t*` arrays on the case VTP. Converter resamples PSA CSVs onto those times (same interp as the AI extractor).

## Converter (legacy / offline)

```bash
# from mclaren-crash-pole, with pyvista available
python scripts/convert_probes_to_global_ts.py scratch/HFuKPb
python scripts/verify_probe_globals.py scratch/HFuKPb
```

**Preferred (Aug 2026+):** declare channels in job-submitted `lsdyna-doe.json`:

```json
"probes": {
  "head_acceleration_y": { "csv": "head_acceleration_y__g.csv" },
  "sensor_uy": { "node_id": 12345, "field": "displacement", "component": "y" }
},
"extract": { "timeseries": ["*"] }
```

CSV wins when present; otherwise AI samples the mesh at `node_id`. Missing sources are omitted. See `examples/mclaren-lsdyna-doe.json` / `mclaren-crash-pole/examples/lsdyna-doe.json`.

Legacy: job-local `probe_map.json` for sparse nodal overlays only (no bundled auto-detect).

See branches `feat/probe-global-timeseries` on `automation-ai-extractor` and `automation-metadata-extractor`.
