# Handoff — McLaren ES-2 side-pole crash extractors (EU Utilities)

**Updated:** 2026-08-05  
**Local path:** `/Users/anicolas/Documents/rescale-projects/mclaren-crash-pole`  
**Remote:** https://github.com/anicolas-rescale/mclaren-crash  
**Gold smoke job:** **`hQdwMb`** (EU) — **Completed, no tile errors** (AI `0.1.12` + Metadata `0.2.14`)  
**Session status:** **Paused / done for now** — extractor path proven. Corpus extract + train blocked on design-space / more-sims call with James Imrie.

## Goal

Post-process McLaren P35 ES-2 side-pole crash results **without an LS-DYNA license**, produce fea-deform VTPs (+ knobs YAML / metadata JSON) suitable for Rescale AI Physics:

`collect_cases` → `initialize_dataset` (`fea-deform`) → `validate_dataset`

## Outcome (how it ended)

Utilities clones of a finished crash (`HFuKPb`) + DEV post-job tiles now reliably emit full-transient `case_data.vtp` / `rescale-ai.vtp` (~711 MB, ~1.3M pts, ~42 frames, PSA probe overlays), `case_data.stl` (~88 MB), knobs-only `case_data.yml` (12 DOE Inputs), and `job_metadata_fields.json`. Knobs resolve from the parent job via **`clonedFrom`** inside metadata `0.2.14` (no need to upload `mclaren_catalog.json` or `export_catalog_from_parent.py` for a smoke). Job-UI custom-fields `/assigned/` can still 400/500; both extractors treat that as **non-fatal** so the tile succeeds when artifacts are good. AI Physics variable UI: globals → **Input**, time-series node vars (`displacement`, `acceleration`, `force`, `moment`, `rib_defl`) → **Output**; single-case “1 warning” is expected.

**Paused here (2026-08-05):** smoke extract is good enough to scale to the starter 23 sync jobs when we resume. Asked James whether the thin OFAT design space was intentional and whether more sims should land before claiming a full-knob toy. Until then, do not promise 12-D interpolation from this corpus alone.

## Status (2026-08-05 — paused)

| Piece | Status |
|--------|--------|
| AI extract on Utilities clone | **Works** — `hQdwMb` (also earlier `aMYNZb` / `hgDZWb`) |
| Metadata Findings (PSA `results.json`) | **Works** — on-disk JSON |
| Metadata DOE Inputs (`mclaren_knobs`) | **Works** — via `clonedFrom` → `case_data.yml` (12 knobs) |
| Custom-fields API → job UI | Soft-fails 400/500 — **non-fatal** in AI `0.1.12` + metadata `0.2.14` |
| Job prep same-path `cp` under `set -e` | **Fixed** — `safe_cp` in `run_job_prep.sh` |
| Extractor images | AI **`0.1.12`**, Metadata **`0.2.14`** |
| Starter-23 corpus extract | **Not started** — ready when unpaused |
| Full 12-knob train claim | **Blocked** — design space too thin (see below) |

**`hQdwMb` outputs (keep these):**

- `rescale-ai.vtp` / `case_data.vtp` (~711 MB)
- `case_data.stl` (~88 MB)
- `case_data.yml` — 12 knobs (`door_inner_mm` 1.2, `ttf_ms` 12, `seat_inb_foam` 1, …)
- `job_metadata_fields.json` — 12 Inputs + Findings (e.g. HIC / rib / pubic peaks)

## What the extractors produce (McLaren)

### AI Surface Extractor

| Content | Source | Need for ~40 scorecard? |
|---------|--------|-------------------------|
| `displacement_t*` (all frames) | `d3plot*` | Yes — fea-deform / GeoTransolver |
| `acceleration_t*` / `force_t*` / `moment_t*` / `rib_defl_t*` on probe nodes | PSA CSVs + `probe_map.json` | Yes — curves → HIC, peaks, VC, … |
| Mesh `NODAL_SCALARS` (von Mises, energy, …) | d3plot element fields | **No** — leave `NODAL_SCALARS=none` |

Probes are **sensor time histories** resampled onto d3plot frame times (~42), not per-element stress fields.

### Metadata Extractor

| Bucket | Expected |
|--------|----------|
| Inputs | DOE knobs (`mclaren_knobs` ← PSA catalog / `clonedFrom` / optional `mclaren_catalog.json`) |
| Findings | Prefer PSA `results.json`; else glstat |
| Context | doe matrix / solver / version |

AI Physics collect prefers **on-disk** `case_data.yml` + VTP over job-page custom fields.

## Working recipe (use this)

### Images (EU ECR)

- AI: `…/deprod-rescale-automation-images-customer:automation-ai-extractor-0.1.12`  
  Digest: `sha256:cd35d24d00f51be932c10abc2007a897c44152a4c6a7b043cfa7c98fcdd9ff50`
- Metadata: `…/deprod-rescale-automation-images-customer:automation-metadata-extractor-0.2.14`

Keep Django tile **Container** tag/digest aligned with `IMG=` inside `run_ai.sh` / `run_metadata.sh`.

### Job setup

1. **Software:** Rescale Utilities (`rescale_utils_lnx`) — no LS-DYNA license.
2. **Inputs:** full crash clone (`d3plot*`, `binout*`, PSA CSVs, `results.json`, …) **plus**:
   - `lsdyna-doe.json` (from `examples/lsdyna-doe.json`)
   - `run_job_prep.sh`
   - `run_ai.sh` (must say **0.1.12**)
   - `run_metadata.sh` (**0.2.14**)
   - Optional: `mclaren_catalog.json` or `export_catalog_from_parent.py` (only if you want knobs on disk before the tile; **not required** when `clonedFrom` points at a PSA parent)
3. **Hardware:** prefer **≥32–72 GB RAM** for full 42-frame mesh (~1.3M pts). Emerald **18 cores / 72 GB** worked. **16 GB OOMs** with default scalars.
4. **Job command:**

   ```bash
   bash run_job_prep.sh
   ```

   Copies launchers to `/enc/tmp` (uses `safe_cp` so same-path copies do not abort under `set -e`).

5. **DEV tiles** (Container = matching image):

   | Tile | Command (only) |
   |------|----------------|
   | AI Surface Extractor [DEV] | `bash /enc/tmp/run_ai.sh` |
   | Metadata Extractor [DEV] | `bash /enc/tmp/run_metadata.sh` |

### What `run_ai.sh` sets

```bash
export AUTOMATION_ANALYSIS=ls_dyna
export NODAL_SCALARS=none          # scorecard does not need mesh stress/strain
export FRAME_POLICY=all            # full transient (~42 frames)
# optional if RAM-constrained: export MAX_FRAMES=12
```

Flow: lock → stage unpack via tile ECR → resolve work dir (`$HOME/work` often has files, not only `shared`) → host `"$VENV_PY" -m automation.main`.

### Scripts in this repo

| Script | Role |
|--------|------|
| `scripts/run_job_prep.sh` | Job command: copy runners → `/enc/tmp` (`safe_cp`) |
| `scripts/run_ai.sh` | Post-job AI launcher (**0.1.12**) |
| `scripts/run_metadata.sh` | Post-job metadata launcher (**0.2.14**) |
| `scripts/export_catalog_from_parent.py` | Optional: materialize `mclaren_catalog.json` from `clonedFrom` |
| `scripts/tile-*-eu-dev.sh` | One-liner tile Commands |
| `scripts/run_extractors.sh` | In-job stage+run (ECR **auth fails** in bare job cmd — avoid) |
| `scripts/wait_for_lsdyna_artifacts.sh` | Earlier experiment — superseded by prep+`/enc/tmp` |

## Lessons learned (do not re-litigate)

1. **Utilities is fine** — PSA/`HFuKPb` was also `rescale_utils_lnx`. Magic was visibility + how Python runs, not LS-DYNA.
2. **Work files often live under `$HOME/work`**, not only `work/shared`. Scripts resolve via `find` for `d3plot*`.
3. **Post-job `bash $HOME/work/shared/run_*.sh` is unsafe** if shared looks empty; **`/enc/tmp` after job-cmd copy** works.
4. **In-job `podman pull` of customer ECR → `authentication required`**. Tile Container object supplies ECR login.
5. **Do not exec Rocky venv inside Alpine** (or PSA as glibc runner for this venv — SSL broke). Stage with Alpine image, run **host** venv.
6. **EU Command UI mangles** fancy paste. Keep tile Command to one `bash /enc/tmp/…` line.
7. Parallel tiles: `/enc/tmp/mclaren-extractor.lock` serializes staging (MEG-1334-class Podman races).
8. **Custom-fields writeback ≠ extract success** — make CF non-fatal; collect uses on-disk VTP/yml.
9. **Knobs on clones:** metadata pulls parent Inputs via `clonedFrom`; uploading `mclaren_catalog.json` is optional insurance.

## AI Physics workstation — next

Proceed with **`hQdwMb`** (or any later clone using the same recipe):

1. `collect_cases` on job `hQdwMb` with patterns `case_data.vtp` + **`case_data.yml`** (+ optional STL).
2. `initialize_dataset(..., dataset_type="fea-deform", surface_file_name="case_data.vtp")`.
3. `validate_dataset`.
4. Variable UI: knobs → Global **Input**; `displacement` / `acceleration` / `force` / `moment` / `rib_defl` → time-series **Output**; disable workspace junk (`Program`, `Stage`, …).

GeoTransolver / Transient: **scalar DOE globals = inputs**; probe curves = **node outputs**. Platform export of extra dynamic channels beyond displacement may still need follow-up for full ~40-from-predicted-VTP.

Single-case UI “1 warning” per variable = low unique-value count — clears with a real multi-case DOE.

## Design space — starter 23 on Rescale (audited 2026-08-05)

Source list: `docs/ls-dyna-extraction-plan.md` starter sync jobs. Pulled EU custom fields for all 23.

| Fact | Detail |
|------|--------|
| Jobs present | 23/23 |
| PSA catalog Inputs | **20/23** — missing CF: `EbjaNb`, `exteNb`, `TAfpEc` (backfill) |
| Sampling | OFAT around Comfort baseline (1.2/1.2 mm, 12 ms, E41, Comfort) |
| Best coverage | `door_inner_mm` (1.1/1.2/1.3), `cavity_foam_gl` (0/60/140) |
| Thin (1–3 off-baseline) | TTF, E22, z-up, bracket cut, brace P16, rail foam, seat inb foam, outer 1.1 |
| Pinned / no signal | `seat_clubsport` = 0 on all 23 (Comfort only) |
| Encoder miss | `cxdsac` has Door Trim `All Wood Fibre` but `trim_woodfibre` stays 0 (`wood fibre` vs `woodfibre` needles) |

**Implication:** enough for pipeline + a reduced-knob / uncertainty smoke. Not enough to freely sweep all ~12 knobs. Options when resuming: freeze inactive knobs, merge Clubsport sheet for seat type, and/or ask McLaren for a designed DOE. Canvas notes: `mclaren-doe-coverage.canvas.tsx`.

### When unpausing

1. Confirm with James / McLaren: more sims vs reduced active knobs.
2. Batch-extract the starter 23 (Utilities clone + prep + DEV tiles) — same recipe as `hQdwMb`.
3. Backfill CF on `EbjaNb` / `exteNb` / `TAfpEc` (or pull from synced-from parents).
4. Optional: fix woodfibre needle (`wood fibre`) in metadata `knobs.py`.
5. `collect_cases` → `initialize` → `validate` → train smoke; use uncertainty to flag thin regions.

### Patch recipe (only if an older collect lacked knobs)

```python
from pathlib import Path
import yaml
from rescale_ai.interactive import DatasetBuilder

case_dir = next(Path.cwd().rglob("case_data.vtp")).parent
GLOBALS = yaml.safe_load(Path("examples/case_data.yml").read_text())
(case_dir / "case_data.yml").write_text(yaml.safe_dump(GLOBALS, sort_keys=False))

builder = DatasetBuilder()
builder.initialize_dataset(
    name="mclaren-crash-smoke",
    dataset_type="fea-deform",
    surface_file_name="case_data.vtp",
    num_workers=4,
)
builder.validate_dataset("mclaren-crash-smoke")
```

Also see `examples/case_data.yml` and `scripts/patch_case_globals.py`.

## Known follow-ups

- [x] DOE knobs on Utilities clone via `clonedFrom` / `case_data.yml`
- [x] Custom-fields `assigned/` failures non-fatal (AI #19 → `0.1.12`; metadata already)
- [x] `run_job_prep.sh` same-path `cp` under `set -e` (`safe_cp`)
- [x] Gold smoke `hQdwMb` + design-space audit of starter 23
- [ ] James / McLaren: intentional OFAT vs more sims for full-knob sweep
- [ ] Batch-extract starter 23 (+ backfill 3 jobs missing catalog CF)
- [ ] Fix `trim_woodfibre` parse for `All Wood Fibre` / `wood fibre`
- [ ] Confirm Transient trains/exports probe channels, not displacement-only
- [ ] Optional: harden CF payload (strip workspace junk) so job-UI stamp succeeds
- [ ] Optional: LS-DYNA `DECIMATION_TARGET`
- [ ] Multi-case DOE scale-out if new sims land

## Key job IDs (EU)

| Job | Note |
|-----|------|
| `HFuKPb` | Original PSA success (Utilities + work mount) — **clone parent** |
| `CtGjQc` | In-job `run_extractors.sh` — ECR auth failed |
| `ZVYgHc` | Prep + tiles; PSA-runner SSL fail; proved host sees `$HOME/work` d3plot |
| `raewMb` | Host launch OK; OOM with default scalars on 16 GB |
| `aMYNZb` | First full VTP success — 72 GB, `NODAL_SCALARS=none` (knobs unresolved) |
| `hgDZWb` | Artifacts good; fail email from prep `cp` + fatal AI CF writeback |
| **`hQdwMb`** | **Gold smoke** — AI `0.1.12` + Meta `0.2.14`, knobs yml, no tile error |

## Related

- Scorecard / probes: `docs/scorecard-field-map.md`; packaged maps in `automation-ai-extractor` `src/core/solvers/ls_dyna/`
- DOE example: `examples/lsdyna-doe.json`
- Xerox nip (separate): `xerox-contact-nip`
- PRs: AI [#17](https://github.com/rescale/automation-ai-extractor/pull/17) (fea-deform), [#18](https://github.com/rescale/automation-ai-extractor/pull/18) (time suffixes), [#19](https://github.com/rescale/automation-ai-extractor/pull/19) (non-fatal CF); Metadata [#25](https://github.com/rescale/automation-metadata-extractor/pull/25) / [#29](https://github.com/rescale/automation-metadata-extractor/pull/29) (globals / `clonedFrom`); McLaren [PR #1](https://github.com/anicolas-rescale/mclaren-crash/pull/1) (`safe_cp`)
