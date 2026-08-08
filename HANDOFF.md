# Handoff — McLaren ES-2 side-pole crash extractors (EU Utilities)

**Updated:** 2026-08-07  
**Local path:** `/Users/anicolas/Documents/rescale-projects/mclaren-crash-pole`  
**Remote:** https://github.com/anicolas-rescale/mclaren-crash  
**Gold smoke job:** **`HLfJXb`** (EU) — AI `0.1.13` + Metadata `0.2.17` (stock tile Commands, no bash helpers)  
**Prior gold:** `hQdwMb` — AI `0.1.12` + Meta `0.2.14` (bash `/enc/tmp` launchers)  
**Session status:** Extractor path proven end-to-end including `collect` → `initialize(fea-deform)` → `validate`. Corpus extract + train still blocked on design-space / James Imrie.

## Goal

Post-process McLaren P35 ES-2 side-pole crash results **without an LS-DYNA license**, produce fea-deform VTPs (+ knobs YAML / metadata JSON) suitable for Rescale AI Physics:

`collect_cases` → `initialize_dataset` (`fea-deform`) → `validate_dataset`

## Outcome (how it ended)

Utilities clone of finished crash (`HFuKPb`) + DEV post-job tiles emit full-transient `case_data.vtp` / `rescale-ai.vtp` (~711 MB, ~1.3M pts, **42** frames, PSA probe overlays), `case_data.stl` (~88 MB), knobs `case_data.yml` (12 DOE Inputs + `psa_description`), and `job_metadata_fields.json` (Inputs + PSA Findings). Knobs resolve from the parent via **`clonedFrom`** + `mclaren_knobs` (metadata ≥ `0.2.14`). Optional: `psa_description` via `custom_field` / `Description`. Job-UI custom-fields `/assigned/` can still 400 — **non-fatal**; collect uses on-disk VTP/yml.

**Preferred recipe (2026-08-07):** Xerox-style stock tile stage+run Commands (EU `deprod` ECR) + upload `lsdyna-doe.json` only — **no** `run_*.sh` helpers required. AI/Meta **`0.1.13` / `0.2.17`** resolve `work/` with d3plot over empty `work/shared`.

**Paused on corpus/train:** starter-23 design space is thin OFAT — do not promise 12-D interpolation until James / more sims.

## Status

| Piece | Status |
|--------|--------|
| AI extract on Utilities clone | **Works** — **`HLfJXb`** (also `hQdwMb` / `aMYNZb` / `hgDZWb`) |
| Metadata Findings (PSA `results.json`) | **Works** |
| Metadata DOE Inputs (`mclaren_knobs`) | **Works** — `clonedFrom` → `case_data.yml` |
| Metadata `custom_field` / `parent_custom_field` | **In ≥`0.2.16`** — McLaren still uses `mclaren_knobs` for parsed PSA strings |
| Stock tiles (no bash helpers) | **Works** — `HLfJXb` |
| Custom-fields API → job UI | Soft-fails 400/500 — non-fatal |
| AI Physics collect → init → validate | **Works** — one-case smoke from `HLfJXb` |
| Extractor images (current) | AI **`0.1.13`**, Metadata **`0.2.17`** |
| Starter-23 corpus extract | **Not started** |
| Full 12-knob train claim | **Blocked** — thin design space |

**`HLfJXb` outputs (keep these):**

- `rescale-ai.vtp` / `case_data.vtp` (~711 MB; ~1.28M pts, 42 times, 12 probes)
- `case_data.stl` (~88 MB)
- `case_data.yml` — 12 knobs (`door_inner_mm` 1.2, `ttf_ms` 12, `seat_inb_foam` 1, …) + `psa_description`
- `job_metadata_fields.json` — 13 Inputs + 14 Findings

## What the extractors produce (McLaren)

### AI Surface Extractor

| Content | Source | Need for ~40 scorecard? |
|---------|--------|-------------------------|
| `displacement_t*` (all frames) | `d3plot*` | Yes |
| probe `acceleration` / `force` / `moment` / `rib_defl` | PSA CSVs + bundled `probe_map` | Yes |
| Mesh `NODAL_SCALARS` | d3plot | **No** — `NODAL_SCALARS=none` |

### Metadata Extractor

| Bucket | Expected |
|--------|----------|
| Inputs | `mclaren_knobs` ← PSA / `clonedFrom` / optional `mclaren_catalog.json`; optional `custom_field` (e.g. `Description` → `psa_description`) |
| Findings | PSA `results.json` preferred |
| Context | doe matrix / solver / version |

## Working recipe (stock tiles — preferred)

### Images (EU ECR)

Same digests as US; host/repo differ:

| Tile | Tag | Digest |
|------|-----|--------|
| AI | `automation-ai-extractor-0.1.13` | `sha256:85449e6b96bd22ce35626a50b2bbc6e2ac25036d988d14feb3b4f8bfaf7fbbf1` |
| Metadata | `automation-metadata-extractor-0.2.17` | `sha256:3b1145682c2d4eba59aa4fc3fad83451971dc27e698c94bdf61378d4af41d4e8` |

```text
631046354827.dkr.ecr.eu-central-1.amazonaws.com/deprod-rescale-automation-images-customer:<tag>
```

**Do not** paste US `us-east-1` / `prod-…` into EU tile Commands — pull fails with `authentication required` (`jjMAac`).

Keep Django tile **Container** tag/digest aligned with Command `IMG=`.

### Job setup

1. **Software:** Rescale Utilities (`rescale_utils_lnx`).
2. **Inputs:** crash clone artifacts (d3plot*, PSA CSVs, `results.json`, …) **plus** `lsdyna-doe.json` from `examples/lsdyna-doe.json`.
3. **Hardware:** ≥32–72 GB RAM for full 42-frame mesh. Emerald 18c / 72 GB worked (`HLfJXb`).
4. **Job command** (no-op; exits 0 so post-job tiles run):

```bash
echo "mclaren postproc — extractors on tiles"
ls -la
find . -maxdepth 3 \( -name 'd3plot' -o -name 'd3plot*' -o -name 'lsdyna-doe.json' \) 2>/dev/null | head -40
```

5. **DEV tiles:** stock stage+run Command (podman → host venv → `automation.main`) with EU `IMG=` above.

### Tile env (UI — not job command)

**AI**

| Var | Value |
|-----|--------|
| `AUTOMATION_ANALYSIS` | `ls_dyna` |
| `NODAL_SCALARS` | `none` |
| `FRAME_POLICY` | `all` |
| `MAX_FRAMES` | `""` (empty — full transient; not `"all"`) |

**Metadata:** `AUTOMATION_ANALYSIS=ls_dyna`

### Optional: bash helpers (legacy)

Still in `scripts/` for `/enc/tmp` launchers (`run_job_prep.sh` + `bash /enc/tmp/run_*.sh`). Prefer stock tiles above; if using helpers, bump `IMG=` in `run_ai.sh` / `run_metadata.sh` to **0.1.13** / **0.2.17** and keep EU `deprod` host.

## Lessons learned (do not re-litigate)

1. Utilities is fine — visibility + host venv mattered, not LS-DYNA software.
2. Results often land under `$HOME/work` (not only `shared`); tiles ≥ `0.1.13` / `0.2.17` prefer a tree that already has d3plot.
3. EU must use `eu-central-1` + `deprod-…` images in Command `IMG=` (and Container).
4. Custom-fields writeback ≠ extract success; collect uses on-disk VTP/yml — include `case_data.yml` in `file_patterns`.
5. Knobs on clones: `clonedFrom` + `mclaren_knobs`; `parent_custom_field` is parent-**only** if you need that semantics.
6. Tile Command UI mangles multi-line `$…` pastes — keep Commands intact or use one-liner helpers.

## AI Physics — proven path

From **`HLfJXb`** (EU API credentials):

```python
builder.collect_cases(
    name="mclaren-p35-hlfjxb-smoke",
    jobs=jobs,  # [HLfJXb]
    file_patterns=["case_data.vtp", "case_data.stl", "case_data.yml"],
)
builder.initialize_dataset(
    name="mclaren-p35-hlfjxb-smoke",
    dataset_type="fea-deform",
    surface_file_name="case_data.vtp",
)
builder.validate_dataset("mclaren-p35-hlfjxb-smoke")
```

- Knobs → Global **Input**; probe / displacement time fields → **Output**
- Local client must use `https://eu.rescale.com` + McLaren EU token (not US platform)

## Design space — starter 23 (audited 2026-08-05)

OFAT around Comfort baseline; thin for full 12-knob train. Details unchanged — see prior table / `mclaren-doe-coverage.canvas.tsx`.

### When unpausing

1. James / McLaren: more sims vs reduced knobs.
2. Batch-extract starter 23 with stock-tile recipe (`HLfJXb`).
3. Backfill CF on `EbjaNb` / `exteNb` / `TAfpEc` (optional; yml is enough for collect).
4. Optional: fix `trim_woodfibre` for `wood fibre`.
5. Train smoke on multi-case fea-deform dataset.

## Known follow-ups

- [x] DOE knobs on Utilities clone via `clonedFrom` / `case_data.yml`
- [x] CF writeback non-fatal
- [x] Gold smoke `hQdwMb` + design-space audit
- [x] Meta **`0.2.17`** + AI **`0.1.13`** EU stock-tile smoke — **`HLfJXb`**
- [x] collect → initialize(`fea-deform`) → validate (one-case)
- [ ] James: OFAT vs more sims
- [ ] Batch-extract starter 23
- [ ] Fix `trim_woodfibre` / `wood fibre`
- [ ] Transient probe-channel train/export confirm

## Key job IDs (EU)

| Job | Note |
|-----|------|
| `HFuKPb` | PSA parent — **clone from here** |
| `jjMAac` | Wrong US ECR in tile Command — auth fail (lesson) |
| `CtGjQc` | In-job extractors — ECR auth failed |
| `ZVYgHc` / `raewMb` / `aMYNZb` / `hgDZWb` | Path to earlier gold (OOM / prep / CF lessons) |
| `hQdwMb` | Prior gold — AI `0.1.12` + Meta `0.2.14` (bash helpers) |
| **`HLfJXb`** | **Current gold** — AI `0.1.13` + Meta `0.2.17`, stock tiles |

## Related

- DOE: `examples/lsdyna-doe.json`
- Xerox nip: `../xerox-contact-nip/HANDOFF.md`
- Metadata PRs: [#29](https://github.com/rescale/automation-metadata-extractor/pull/29) `clonedFrom`; [#31](https://github.com/rescale/automation-metadata-extractor/pull/31) nip; [#32](https://github.com/rescale/automation-metadata-extractor/pull/32) `scale` / `custom_field`; [#33](https://github.com/rescale/automation-metadata-extractor/pull/33) SyntaxError hotfix → **`0.2.17`**
- AI PRs: [#17](https://github.com/rescale/automation-ai-extractor/pull/17)–[#20](https://github.com/rescale/automation-ai-extractor/pull/20) → **`0.1.13`**
- McLaren [PR #1](https://github.com/anicolas-rescale/mclaren-crash/pull/1) (`safe_cp`)
