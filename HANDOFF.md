# Handoff — McLaren ES-2 side-pole crash extractors (EU Utilities)

**Updated:** 2026-08-20

> **GeoTransolver global TS — almost across the finish line.** Clean PSA→YAML re-extract (`crashPostProcOK`, 18 cases) trained 200 epochs on Grossular `cXBNn`. PR [rescale-ai#1217](https://github.com/rescale/rescale-ai/pull/1217): Guangchen liked it (2026-08-20), will review this afternoon, then merge + test in **dev**. Notes: [`.claude/handoffs/2026-08-18-transient-global-ts.md`](./.claude/handoffs/2026-08-18-transient-global-ts.md). Do **not** use the old 39-channel holdout numbers (`docs/geotransolver-holdout-2026-08/`) — those labels were poisoned.
>
> **Variables UI OOM (Aug 2026) — DONE.** Merged [#1186](https://github.com/rescale/rescale-ai/pull/1186). Write-up: [`docs/handoff-2026-08-variables-ui-oom-fix.md`](./docs/handoff-2026-08-variables-ui-oom-fix.md).

**Local path:** `/Users/anicolas/Documents/rescale-projects/mclaren-crash-pole`  
**Remote:** https://github.com/anicolas-rescale/mclaren-crash  
**Gold smoke job:** **`HLfJXb`** (EU) — AI `0.1.13` + Metadata `0.2.17` (stock tile Commands, no bash helpers)  
**Prior gold:** `hQdwMb` — AI `0.1.12` + Meta `0.2.14` (bash `/enc/tmp` launchers)  
**Session status:** Starter-23 extract **done**. Clean PSA-probe re-extract tagged `crashPostProcOK` (18 jobs) was collected/trained on `cXBNn`. Old HxPaa `crashPostProcess` corpus is the **poisoned** YAML set. Next: Guangchen formal review + merge of #1217, then Dev smoke. More cases later if we care about door-inner displacement.

## Goal

Post-process McLaren P35 ES-2 side-pole crash results **without an LS-DYNA license**, produce fea-deform VTPs (+ knobs YAML / metadata JSON) suitable for Rescale AI Physics:

`collect_cases` → `initialize_dataset` (`fea-deform`) → `validate_dataset`

## Outcome (how it ended)

Utilities clone of finished crash (`HFuKPb`) + DEV post-job tiles emit full-transient `case_data.vtp` / `rescale-ai.vtp` (~711 MB, ~1.3M pts, **42** frames, PSA probe overlays), `case_data.stl` (~88 MB), knobs `case_data.yml` (12 DOE Inputs + `psa_description`), and `job_metadata_fields.json` (Inputs + PSA Findings). Knobs resolve from the parent via **`clonedFrom`** + `mclaren_knobs` (metadata ≥ `0.2.14`). Optional: `psa_description` via `custom_field` / `Description`. Job-UI custom-fields `/assigned/` can still 400 — **non-fatal**; collect uses on-disk VTP/yml.

**Preferred recipe (2026-08-07):** Xerox-style stock tile stage+run Commands (EU `deprod` ECR) + upload `lsdyna-doe.json` only — **no** `run_*.sh` helpers required. AI/Meta **`0.1.13` / `0.2.17`** resolve `work/` with d3plot over empty `work/shared`.

**Batch extract (2026-08-11):** Script `scripts/batch_extract_clones.py` reproduced the `HLfJXb` recipe for the James starter set — pilot `ctowac`→`gNHKPb`, then serial remainder. Manifest: `scripts/batch_extract_manifest.csv`. All extracts tagged `crashPostProcess` and moved to folder **`HxPaa`**.

**Train caveat:** starter-23 design space is still thin OFAT — do not promise 12-D interpolation until James / more sims. Collect on the 18 is unblocked.

## Status

| Piece | Status |
|--------|--------|
| AI extract on Utilities clone | **Works** — **`HLfJXb`** (+ batch children below) |
| Metadata Findings (PSA `results.json`) | **Works** |
| Metadata DOE Inputs (`mclaren_knobs`) | **Works** — `clonedFrom` → `case_data.yml` (needs Door/TTF on parent) |
| Metadata `custom_field` / `parent_custom_field` | **In ≥`0.2.16`** — McLaren still uses `mclaren_knobs` for parsed PSA strings |
| Stock tiles (no bash helpers) | **Works** — `HLfJXb` |
| Custom-fields API → job UI | Soft-fails 400/500 — non-fatal |
| AI Physics collect → init → validate | **Works** — 18-case `crashPostProcOK` dataset on `cXBNn` (`mclaren-p35-side-pole-18-probes`) |
| Extractor images (current) | AI **`0.1.13`**, Metadata **`0.2.17`** |
| Starter-23 corpus extract | **Done** — 19 cloned, **18** train-ready; see table |
| Full 12-knob train claim | **Still thin OFAT** — collect OK; interpolation claim blocked |

**`HLfJXb` outputs (keep these):**

- `rescale-ai.vtp` / `case_data.vtp` (~711 MB; ~1.28M pts, 42 times, 12 probes)
- `case_data.stl` (~88 MB)
- `case_data.yml` — 12 knobs (`door_inner_mm` 1.2, `ttf_ms` 12, `seat_inb_foam` 1, …) + `psa_description`
- `job_metadata_fields.json` — 13 Inputs + 14 Findings

---

## Starter-23 batch extract (2026-08-11)

### Scoreboard

| Bucket | Count | IDs |
|--------|------:|-----|
| James starter sync jobs | 23 | see table |
| Collect / train ready | **18** | all OK rows below |
| Extracted but **skip for train** | 1 | `exteNb` → `wAZOQc` |
| Never extracted (`surrogate:exclude*`) | 4 | `ifkFPb`, `MUjFPb`, `EbjaNb`, `TAfpEc` |

**Folder:** [Side_Pole_Data_Occupant `HxPaa`](https://eu.rescale.com/folders/HxPaa/)  
**Queue filter used:** loadcase tag `psaf:loadcase:os_es2re_pole32`, skip any tag starting `surrogate:exclude`  
**DOE file reused:** `catYzo` (`examples/lsdyna-doe.json` upload)

### Job chain table

Chain = **Extract (postproc Utilities clone)** ← **Sync parent (clonedFrom)** ← **Original LS-DYNA solver** (`rescale-cli sync -j …`).

| Status | Case | Extract | Sync parent | Original solver | Notes |
|--------|------|---------|-------------|-----------------|-------|
| OK | Inboard seat foam CAE HP | **HLfJXb** | HFuKPb | HViTQc | Gold / manual; 12 knobs |
| OK | E22 + airbag up 30mm | gNHKPb | ctowac | eiqgFc | Pilot; 12 knobs |
| OK | E41 airbag up 30mm | raMAac | OQuKPb | giqgFc | Batch OK |
| OK | E22 + bracket cut | SicTPb | Qhowac | XFOYWb | Batch OK |
| OK | Bracket cut | PUfJXb | BFuKPb | QZYOQc | Batch OK |
| OK | Cavity 60gl + outer 1.1mm | odxaNb | MQuKPb | EfqgFc | Batch OK |
| OK | Cavity 60gl + inner 1.3mm | EDGeNb | zFuKPb | RHiTQc | Batch OK |
| OK | Cavity 60gl + inner 1.1mm | GRKVXb | xHdsac | mFfcFc | Batch OK |
| **Excluded** | Outer 1.1mm | — | ifkFPb | AmPKQc | `surrogate:exclude:duplicate-wrong-deck` — keep `ixdsac` |
| OK | Inner 1.3mm | bcLVXb | gfkFPb | NwPKQc | Batch OK |
| OK | Inner 1.1mm | JDrsac | ixdsac | AmPKQc | Batch OK |
| OK | Cavity 140gl | KdFFQc | UUjFPb | ymPKQc | Batch OK |
| OK | Door brace P16 | UdFFQc | pHdsac | jwzzMb | Batch OK |
| OK | Rail foam | HPPKQc | afkFPb | eDEFQc | Batch OK |
| OK | Woodfibre trim | aYQpTc | cxdsac | SaMTEc | Batch OK |
| OK | Cavity 60gl | WvXCHc | OUjFPb | jKVXEc | Batch OK |
| OK | E22 airbag | kDBQHc | YekFPb | emMTEc | Batch OK |
| OK | TTF 9ms | fcWXEc | axdsac | sCuCTc | Batch OK |
| **Excluded** | Countermeasures plus | — | MUjFPb | hmESPc | `surrogate:exclude:configuration-conflict` |
| OK | Base ISF 207c | oAZOQc | vVwVXb | vNXdac | Batch OK |
| **Excluded** | Outer 1.3mm | — | EbjaNb | NwPKQc | `surrogate:exclude:duplicate-wrong-deck` — keep `gfkFPb`; also no Door/TTF match |
| **Skip train** | Base ISF 004 b003 | wAZOQc | exteNb | eDoBSc | Mesh OK (~692 MB VTP); **9 knobs only** — see below |
| **Excluded** | Base ISF 004 duplicate | — | TAfpEc | eDoBSc | `surrogate:exclude:incomplete-duplicate` |

### Collect-ready extract IDs (18)

```text
HLfJXb gNHKPb raMAac SicTPb PUfJXb odxaNb EDGeNb GRKVXb bcLVXb JDrsac
KdFFQc UdFFQc HPPKQc aYQpTc WvXCHc kDBQHc fcWXEc oAZOQc
```

Do **not** include `wAZOQc` unless Door/TTF are backfilled on `exteNb` (or catalog patched into the extract).

### Why `exteNb` / `wAZOQc` is skipped

1. **Passive Safety Automation did not fail on “hic limit” Inputs.** PSA `0.1.52` on `exteNb` logged `Posted 10 findings, 10 inputs and 2 context fields` — those 10 inputs are injury **limits** (`hic36Limit`, `t12A3msLimit`, …). Same line appears on healthy peers.
2. **Door / TTF / Airbag / Seat are not from that PSA post.** They come from a separate **config match** against the run-log sheet (`Config Match Status = unambiguous` on good jobs).
3. On `exteNb`, config match **never wrote** Door/TTF (`Config Match Status` absent). Sync source `eDoBSc` (and `clonedFrom` `hDuKPb`) are **404**. Run log still has the `eDoBSc` row (Comfort Seat Base - ISF 004 b003 → Door 1.2mm / TTF 12ms), but **ISF 004 b003 also has a Clubsport twin** → ambiguous match risk. Same thin catalog on `TAfpEc` / `EbjaNb`.
4. Metadata `mclaren_knobs` only emits `door_inner_mm` / `door_outer_mm` / `ttf_ms` when those catalog fields exist; boolean knobs still default → **9 knobs** on `wAZOQc`.

**Decision (Andrea 2026-08-12):** skip this case for train; optional later backfill from run-log `eDoBSc` row if needed.

### Batch tooling

| Artifact | Path / note |
|----------|-------------|
| Batch script | `scripts/batch_extract_clones.py` (`--dry-run` / `--pilot` / `--serial`, `--folder-id HxPaa`) |
| Manifest | `scripts/batch_extract_manifest.csv` |
| Logs | `scripts/pilot_ctowac.log`, `scripts/serial_extract.log` |
| Catalog export helper | `scripts/export_catalog_from_parent.py` |
| Knob patch helper | `scripts/patch_case_globals.py` |
| Visual status canvas | Cursor canvas `mclaren-starter23-extract-status.canvas.tsx` (workspace canvases dir) |

---

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
| Inputs | `mclaren_knobs` ← PSA catalog / `clonedFrom` / optional `mclaren_catalog.json`; optional `custom_field` (e.g. `Description` → `psa_description`) |
| Findings | PSA `results.json` preferred |
| Context | doe matrix / solver / version |

**Important:** PSA injury-limit Inputs ≠ DOE catalog. Training knobs need Door Inner / Outer / TTF / Airbag / … (or a `mclaren_catalog.json` on the extract job).

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

1. **Software:** Rescale Utilities (`rescale_utils_lnx` / `v2025.12.16-sxp`).
2. **Inputs:** crash clone artifacts (d3plot*, PSA CSVs, `results.json`, …) **plus** `lsdyna-doe.json` from `examples/lsdyna-doe.json`.
3. **Hardware:** ≥32–72 GB RAM for full 42-frame mesh. Emerald 18c / 72 GB worked (`HLfJXb`).
4. **Job command** (no-op; exits 0 so post-job tiles run):

```bash
echo "mclaren postproc — extractors on tiles"
ls -la
find . -maxdepth 3 \( -name 'd3plot' -o -name 'd3plot*' -o -name 'lsdyna-doe.json' \) 2>/dev/null | head -40
```

5. **DEV tiles:** Metadata `Bwuia` + AI Surface `QYnVk` with env below; tag **`crashPostProcess`** (+ keep loadcase tag when present).
6. **Move** completed extracts to folder **`HxPaa`**.

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
7. **PSA “10 inputs” = injury limits**, not Door/TTF. DOE catalog needs config match (or manual/`mclaren_catalog.json` backfill). Missing match → thin `case_data.yml` even when VTP is fine.
8. Honor James `surrogate:exclude*` tags — duplicates / wrong deck / config conflicts.

## AI Physics — next (18-case collect)

From the **18** extract IDs above (EU API credentials):

```python
builder.collect_cases(
    name="mclaren-p35-side-pole-18",
    jobs=jobs,  # 18 extract IDs — exclude wAZOQc
    file_patterns=["case_data.vtp", "case_data.stl", "case_data.yml"],
)
builder.initialize_dataset(
    name="mclaren-p35-side-pole-18",
    dataset_type="fea-deform",
    surface_file_name="case_data.vtp",
)
builder.validate_dataset("mclaren-p35-side-pole-18")
```

- Knobs → Global **Input**; probe / displacement time fields → **Output**
- Local client must use `https://eu.rescale.com` + McLaren EU token (not US platform)
- One-case smoke already proven on `HLfJXb`

## Design space — starter 23 (audited 2026-08-05)

OFAT around Comfort baseline; thin for full 12-knob train. Details in `docs/ls-dyna-extraction-plan.md` and prior DOE coverage canvas.

### When continuing

1. Collect → init → validate on the **18** (above).
2. James / McLaren: more sims vs reduced knobs before claiming 12-D surrogate.
3. Optional: backfill Door/TTF on `exteNb` from run-log `eDoBSc` row, re-run metadata on `wAZOQc` (or patch yml) if you want 19.
4. Optional: fix `trim_woodfibre` for `wood fibre`.
5. **GeoTransolver joint outputs** — plan [`docs/geotransolver-global-ts-plan.md`](docs/geotransolver-global-ts-plan.md). **Phase 0–1 done:** branch `feat/transient-global-ts-outputs`, schema [`docs/probe-global-schema.md`](docs/probe-global-schema.md), converter `scripts/convert_probes_to_global_ts.py` (smoke `scratch/HFuKPb` → `[42, 37]`). Next: Phase 2 implementation on that branch.

## Known follow-ups

- [x] DOE knobs on Utilities clone via `clonedFrom` / `case_data.yml`
- [x] CF writeback non-fatal
- [x] Gold smoke `hQdwMb` + design-space audit
- [x] Meta **`0.2.17`** + AI **`0.1.13`** EU stock-tile smoke — **`HLfJXb`**
- [x] collect → initialize(`fea-deform`) → validate (one-case)
- [x] Batch-extract starter 23 (18 train-ready; 1 skip; 4 tag-excludes)
- [ ] Collect / init / validate multi-case (18)
- [ ] James: OFAT vs more sims
- [ ] Optional backfill `exteNb` / `wAZOQc` Door/TTF
- [x] Fix `trim_woodfibre` / `wood fibre` — manual flip on dataset `mclaren-p35-side-pole-19` case `case4_aYQpTc` (extract `aYQpTc`) 0→1; catalog parse still broken upstream
- [ ] GeoTransolver nodal + global-TS probes — [`docs/geotransolver-global-ts-plan.md`](docs/geotransolver-global-ts-plan.md)

## Key job IDs (EU)

| Job | Note |
|-----|------|
| `HFuKPb` | PSA parent — gold clone source |
| **`HLfJXb`** | **Gold extract** — AI `0.1.13` + Meta `0.2.17`, stock tiles |
| `HxPaa` | Folder for all batch extracts |
| `wAZOQc` | Extract from `exteNb` — **skip train** (knob gap) |
| `jjMAac` | Wrong US ECR in tile Command — auth fail (lesson) |
| `CtGjQc` | In-job extractors — ECR auth failed |
| `ZVYgHc` / `raewMb` / `aMYNZb` / `hgDZWb` | Path to earlier gold (OOM / prep / CF lessons) |
| `hQdwMb` | Prior gold — AI `0.1.12` + Meta `0.2.14` (bash helpers) |

## Related

- DOE: `examples/lsdyna-doe.json`
- Plan / sync→solver map: `docs/ls-dyna-extraction-plan.md`
- Run log (local): `P35_ES2_Side_Pole_Run_Log(2)/`
- Xerox nip: `../xerox-contact-nip/HANDOFF.md`
- Metadata PRs: [#29](https://github.com/rescale/automation-metadata-extractor/pull/29) `clonedFrom`; [#31](https://github.com/rescale/automation-metadata-extractor/pull/31) nip; [#32](https://github.com/rescale/automation-metadata-extractor/pull/32) `scale` / `custom_field`; [#33](https://github.com/rescale/automation-metadata-extractor/pull/33) SyntaxError hotfix → **`0.2.17`**
- AI PRs: [#17](https://github.com/rescale/automation-ai-extractor/pull/17)–[#20](https://github.com/rescale/automation-ai-extractor/pull/20) → **`0.1.13`**
- McLaren [PR #1](https://github.com/anicolas-rescale/mclaren-crash/pull/1) (`safe_cp`)
