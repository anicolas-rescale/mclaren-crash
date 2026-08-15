# Plan — McLaren data prep (Kyanite): proper time-series globals

**WS:** `udeprod_Qqqwb@54.216.200.104` (Kyanite, 4c / 32 GB, no GPU)  
**HPS:** `storage_wtaTdb`  
**Goal:** dataset Variables UI shows the right I/O shape (prep only — no GeoTransolver train yet)

## Target shape

| Role | Variables | UI bucket |
|------|-----------|-----------|
| **Inputs** | DOE knobs (`door_inner_mm`, `ttf_ms`, …) | Global variables |
| **Outputs** | `displacement_t*` | Time series **node** variables |
| **Outputs** | probe channels (`head_acceleration_x`, forces, moments, ribs, …) | Time series **global** variables |
| **Disabled** | sparse nodal `acceleration` / `force` / `moment` / `rib_defl` | (keep off) |
| **Disabled** | `psa_description`, `seat_clubsport` | already off — keep |

## What’s on HPS now (checked)

| Path | State |
|------|--------|
| `datasets/mclaren-p35-side-pole-19` | **18 cases**, each `case_data.yml` has `timeseries:` with **G=39**, **T=41**, key still named **`times`** (not `timesteps`) |
| `datasets/.../versionMetadata.yaml` | knobs OK (11 inputs); displacement enabled; probe **node** fields disabled; probe globals present as **bare names** (not `_t0.000`) → show under plain Global Variables |
| `scratch/mclaren-p35-side-pole-19` | **empty husk** (no case folders) — cannot initialize from scratch as-is |
| Disk | datasets ~14 GB; HPS free ~284 GB |

## Why re-init (not just leave bare names)

Platform UI groups **Time Series Global Variables** only when names match `_t0.000`, `_t0.002`, ….  
`initialize_dataset` expands `case_data.yml` → `timeseries:` into those `_t*` global output entries (via `file_utils`).

## OOM rules (32 GB Kyanite)

- **`num_workers=1`** on initialize + validate (always)
- Do **not** open VTPs in parallel for prep
- Agent work that only touches YAML = cheap; initialize/validate still reads VTPs serially — slower, safer
- Do **not** start training on this box

## Steps

### A — Agent (no Jupyter): YAML hygiene on `datasets/`

1. Rename `timeseries.times` → `timeseries.timesteps` on all 18 `case_data.yml` (in place under `datasets/`).
2. Spot-check one case: `timesteps` present, G=39, T=41, knobs intact.

**Status: DONE** — 18/18 renamed; backup at `/enc/udeprod_Qqqwb/mclaren_probe_convert/backup_pre_reinit/`

### B — Agent (no Jupyter): rebuild `scratch/` for initialize

`initialize_dataset` / `validate_dataset` only look at **scratch**, then validate **replaces** `datasets/`.

1. Remove empty scratch husk (or clear `cases/`).
2. Copy `datasets/mclaren-p35-side-pole-19` → `scratch/mclaren-p35-side-pole-19`  
   (~14 GB; HPS has room). Prefer `cp -a` / `rsync` of the whole tree so versions + cases stay consistent before init rewrites metadata.
3. Confirm scratch has 18 cases with `timeseries.timesteps`.

**Status: DONE** — scratch has 18/18 ready with timesteps+G39

### C — **You (Jupyter notebook):** initialize + validate

**Status: DONE** — initialize wrote TS global metadata; validate finalized dataset. Agent patched flags post-validate.

### D — Agent after you confirm Jupyter finished: verify + UI checklist

**Status: DONE** — see summary below / in chat.

Final metadata shape on `datasets/mclaren-p35-side-pole-19`:
- 11 knob global **inputs** enabled (`seat_clubsport` / `psa_description` disabled)
- 39 probe bases × 41 steps = **1599** global TS **outputs** (`*_t0.000`…)
- `timesteps` junk group **disabled**
- node: `displacement` enabled; `acceleration`/`force`/`moment`/`rib_defl` disabled

Paste / run:

```python
from rescale_ai.interactive import DatasetBuilder

builder = DatasetBuilder()
DATASET = "mclaren-p35-side-pole-19"

# Do NOT collect_cases again.

builder.initialize_dataset(
    name=DATASET,
    dataset_type="fea-deform",
    surface_file_name="case_data.vtp",
    num_workers=1,  # required on 32 GB
)

builder.validate_dataset(DATASET, num_workers=1)  # moves scratch → datasets/
```

**Expect:** initialize takes a while (serial VTP reads). If memory climbs badly, stop and tell me — don’t raise workers.

**Side effect:** validate deletes old `datasets/...` and moves scratch into its place. That’s intended; converted YAMLs must be in scratch first (step B).

### D — Agent after you confirm Jupyter finished: verify + UI checklist

1. Check `datasets/.../versionMetadata.yaml`:
   - global inputs = knobs (enabled)
   - global outputs = `*_t0.000` style probe channels (many rows / grouped)
   - node outputs = `displacement_t*` enabled; `acceleration`/`force`/`moment`/`rib_defl` disabled
2. You refresh dataset Variables in the UI:
   - **Time Series Global Variables** — probe groups
   - **Time Series Node Variables** — `displacement`
   - **Global variables** — knobs only (plus maybe junk)
3. If a **`timesteps`** time-series group appears → **disable it** (platform expands that key; cosmetic junk).

## Explicit non-goals this round

- GeoTransolver training / Grossular
- Extractor tile changes
- Re-collect from jobs
- Touching `feat/transient-global-ts-outputs` code (Phase 2 later)

## Rollback

- Pre-init: datasets already has good YAMLs; only risk is mid-copy.
- Post-validate wipe: if validate fails mid-move, tell me before re-running; we can restore from HPS if needed.
- Optional: before step B, I can snapshot `versionMetadata.yaml` + one yml under `mclaren_probe_convert/backup_…`.

## Decision needed from you

Approve this plan (A → B → you run C → D), or prefer a **metadata-only** expand (no initialize/validate, lower risk, slightly less “official”)?
