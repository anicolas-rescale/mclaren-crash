# Handoff — McLaren ES-2 side-pole crash extractors (EU Utilities)

**Updated:** 2026-08-07  
**Local path:** `/Users/anicolas/Documents/rescale-projects/mclaren-crash-pole`  
**Remote:** https://github.com/anicolas-rescale/mclaren-crash  
**Gold smoke job:** **`hQdwMb`** (EU) — AI `0.1.12` + Metadata `0.2.14`  
**Next smoke:** Metadata **`0.2.16`** (+ updated `examples/lsdyna-doe.json`) — clone recipe same as `hQdwMb`  
**Session status:** Extractor path proven; corpus extract + train still blocked on design-space / James Imrie. Re-smoke Meta `0.2.16` when convenient.

## Goal

Post-process McLaren P35 ES-2 side-pole crash results **without an LS-DYNA license**, produce fea-deform VTPs (+ knobs YAML / metadata JSON) suitable for Rescale AI Physics:

`collect_cases` → `initialize_dataset` (`fea-deform`) → `validate_dataset`

## Outcome (how it ended)

Utilities clones of a finished crash (`HFuKPb`) + DEV post-job tiles reliably emit full-transient `case_data.vtp` / `rescale-ai.vtp` (~711 MB, ~1.3M pts, ~42 frames, PSA probe overlays), `case_data.stl` (~88 MB), knobs-only `case_data.yml` (12 DOE Inputs), and `job_metadata_fields.json`. Knobs resolve from the parent via **`clonedFrom`** + `mclaren_knobs` (metadata ≥ `0.2.14`; current target **`0.2.16`**). Optional raw field: `psa_description` via `custom_field` / `Description`. Job-UI custom-fields `/assigned/` can still 400/500 — **non-fatal**. AI Physics: globals → **Input**; time-series node vars → **Output**.

**Paused (2026-08-05) on corpus/train:** starter-23 design space is thin OFAT — do not promise 12-D interpolation until James / more sims.

## Status

| Piece | Status |
|--------|--------|
| AI extract on Utilities clone | **Works** — `hQdwMb` (also `aMYNZb` / `hgDZWb`) |
| Metadata Findings (PSA `results.json`) | **Works** |
| Metadata DOE Inputs (`mclaren_knobs`) | **Works** — `clonedFrom` → `case_data.yml` |
| Metadata `custom_field` / `parent_custom_field` | **In `0.2.16`** — parent-only source available; McLaren still uses `mclaren_knobs` for parsed PSA strings |
| Custom-fields API → job UI | Soft-fails 400/500 — non-fatal |
| Job prep same-path `cp` | **Fixed** — `safe_cp` |
| Extractor images (smoke target) | AI **`0.1.12`**, Metadata **`0.2.16`** |
| Starter-23 corpus extract | **Not started** |
| Full 12-knob train claim | **Blocked** — thin design space |

**`hQdwMb` outputs (keep these):**

- `rescale-ai.vtp` / `case_data.vtp` (~711 MB)
- `case_data.stl` (~88 MB)
- `case_data.yml` — 12 knobs (`door_inner_mm` 1.2, `ttf_ms` 12, `seat_inb_foam` 1, …)
- `job_metadata_fields.json` — 12 Inputs + Findings

## What the extractors produce (McLaren)

### AI Surface Extractor

| Content | Source | Need for ~40 scorecard? |
|---------|--------|-------------------------|
| `displacement_t*` (all frames) | `d3plot*` | Yes |
| probe `acceleration` / `force` / `moment` / `rib_defl` | PSA CSVs + `probe_map` | Yes |
| Mesh `NODAL_SCALARS` | d3plot | **No** — `NODAL_SCALARS=none` |

### Metadata Extractor

| Bucket | Expected |
|--------|----------|
| Inputs | `mclaren_knobs` ← PSA / `clonedFrom` / optional `mclaren_catalog.json`; optional `custom_field` (e.g. `Description` → `psa_description`) |
| Findings | PSA `results.json` preferred |
| Context | doe matrix / solver / version |

## Working recipe

### Images (EU ECR)

- AI: `…/deprod-rescale-automation-images-customer:automation-ai-extractor-0.1.12`  
  Digest: `sha256:cd35d24d00f51be932c10abc2007a897c44152a4c6a7b043cfa7c98fcdd9ff50`
- Metadata: `…/deprod-rescale-automation-images-customer:automation-metadata-extractor-0.2.16`  
  Digest: `sha256:27f0adf37b48a32db5e93993f1032aa7fc5de7e33ca5bcc3708b2ed9d060bb7c`

Keep Django tile **Container** tag/digest aligned with `IMG=` in `run_ai.sh` / `run_metadata.sh`.

### Job setup

1. **Software:** Rescale Utilities (`rescale_utils_lnx`).
2. **Inputs:** crash clone artifacts **plus**:
   - `lsdyna-doe.json` (from `examples/lsdyna-doe.json` — includes optional `psa_description`)
   - `run_job_prep.sh`, `run_ai.sh` (**0.1.12**), `run_metadata.sh` (**0.2.16**)
3. **Hardware:** ≥32–72 GB RAM for full 42-frame mesh. Emerald 18c / 72 GB worked; 16 GB OOMs with default scalars.
4. **Job command:** `bash run_job_prep.sh`
5. **DEV tiles:** Command only — `bash /enc/tmp/run_ai.sh` / `bash /enc/tmp/run_metadata.sh`

### What `run_ai.sh` sets

```bash
export AUTOMATION_ANALYSIS=ls_dyna
export NODAL_SCALARS=none
export FRAME_POLICY=all
```

### Scripts

| Script | Role |
|--------|------|
| `scripts/run_job_prep.sh` | Copy runners → `/enc/tmp` (`safe_cp`) |
| `scripts/run_ai.sh` | AI launcher (**0.1.12**) |
| `scripts/run_metadata.sh` | Metadata launcher (**0.2.16**) |
| `scripts/tile-*-eu-dev.sh` | One-liner tile Commands |
| `scripts/run_extractors.sh` | In-job stage+run — ECR auth fails in bare job cmd; Meta tag **0.2.16** |

## Lessons learned (do not re-litigate)

1. Utilities is fine — visibility + host venv mattered, not LS-DYNA software.
2. Work files often under `$HOME/work`, not only `shared`.
3. Prefer `/enc/tmp` launchers after job-cmd copy.
4. Tile Command UI mangles `$…` pastes — one `bash /enc/tmp/…` line.
5. Custom-fields writeback ≠ extract success; collect uses on-disk VTP/yml.
6. Knobs on clones: `clonedFrom` + `mclaren_knobs`; `parent_custom_field` is parent-**only** if you need that semantics.

## AI Physics workstation — next

Use **`hQdwMb`** (or a fresh `0.2.16` clone):

1. `collect_cases` — `case_data.vtp` + `case_data.yml`
2. `initialize_dataset(..., dataset_type="fea-deform")`
3. `validate_dataset`
4. Knobs → Global **Input**; probe channels → **Output**

## Design space — starter 23 (audited 2026-08-05)

OFAT around Comfort baseline; thin for full 12-knob train. Details unchanged — see prior table / `mclaren-doe-coverage.canvas.tsx`.

### When unpausing

1. James / McLaren: more sims vs reduced knobs.
2. Re-smoke Meta **`0.2.16`**, then batch-extract starter 23.
3. Backfill CF on `EbjaNb` / `exteNb` / `TAfpEc`.
4. Optional: fix `trim_woodfibre` for `wood fibre`.
5. `collect` → `initialize` → `validate` → train smoke.

## Known follow-ups

- [x] DOE knobs on Utilities clone via `clonedFrom` / `case_data.yml`
- [x] CF writeback non-fatal
- [x] Gold smoke `hQdwMb` + design-space audit
- [ ] Meta **`0.2.16`** EU smoke (updated DOE JSON)
- [ ] James: OFAT vs more sims
- [ ] Batch-extract starter 23
- [ ] Fix `trim_woodfibre` / `wood fibre`
- [ ] Transient probe-channel train/export confirm

## Key job IDs (EU)

| Job | Note |
|-----|------|
| `HFuKPb` | PSA parent — **clone from here** |
| `CtGjQc` | In-job extractors — ECR auth failed |
| `ZVYgHc` / `raewMb` / `aMYNZb` / `hgDZWb` | Path to gold (OOM / prep / CF lessons) |
| **`hQdwMb`** | Gold smoke — AI `0.1.12` + Meta `0.2.14` |

## Related

- DOE: `examples/lsdyna-doe.json`
- Xerox nip: `../xerox-contact-nip/HANDOFF.md`
- Metadata PRs: [#29](https://github.com/rescale/automation-metadata-extractor/pull/29) `clonedFrom`; [#31](https://github.com/rescale/automation-metadata-extractor/pull/31) nip; [#32](https://github.com/rescale/automation-metadata-extractor/pull/32) `scale` / `custom_field` / `parent_custom_field` → **`0.2.16`**
- AI PRs: [#17](https://github.com/rescale/automation-ai-extractor/pull/17)–[#20](https://github.com/rescale/automation-ai-extractor/pull/20)
- McLaren [PR #1](https://github.com/anicolas-rescale/mclaren-crash/pull/1) (`safe_cp`)
