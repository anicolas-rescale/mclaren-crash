# Plan — GeoTransolver: nodal displacement + global probe time series

**Created:** 2026-08-12  
**Owners:** Andre (+ Guangchen review)  
**Repos:** `rescale-ai` (feature branch) · `mclaren-crash-pole` (data conversion / notes) · extractor tiles **deferred**  
**Why not MGN:** McLaren meshes are ~1.28M pts × ~40 frames, targeting hundreds of cases. MGN’s graph path is impractical at that scale (GMI box was tiny). Use GeoTransolver; **steal the MGN global-TS pattern**, don’t run MGN.

## Goal

Train Transient **GeoTransolver** so that:

| Role | Variables | Shape (conceptual) |
|------|-----------|--------------------|
| **Inputs** | Existing DOE knobs (scalar globals) | `G_in` scalars per case |
| **Nodal output** | `displacement` time series | `[N, T, 3]` |
| **Global outputs** | ~12 probe histories (force / moment / acc / rib_defl) | `[T, G_out]` |

Inference / eval must return both the deformed field and the probe curves (scorecard path).

## Non-goals (this branch)

- Full AutomL / UI polish beyond what training needs
- Perfect extractor rewrite (Phase B, deferred)
- Claiming a production McLaren surrogate (starter set is still thin OFAT)
- Porting TwoStream global decoder as-is (different stack; optional later inspiration only)

---

## Phase 0 — Branch + reference study

1. From local `rescale-ai` `main` (keep current):
   ```bash
   git fetch origin
   git checkout -b feat/transient-global-ts-outputs origin/main
   ```
2. Read / annotate Guangchen’s FEA MGN pattern (do **not** copy graph ops):
   - `rescale_ai/models/fea_model.py` — `outvar_ts_keys`, `global_output_dim`
   - `rescale_ai/solver/fea/datapipe.py` — load globals from `case_data.yml` timeseries → `outvar_ts [T, G]`
   - `rescale_ai/solver/fea/rollout.py` — `MeshGraphNetTimeConditionalRollout`: mean-pool latent → MLP → `[T, G]` alongside `[T, N, 3]`
   - `rescale_ai/solver/fea/train.py` — joint loss (node + global; note loss-weight balancing)
3. Skim Transient blockers today:
   - `rescale_ai/models/transient_model.py` — **rejects** time-series globals
   - `rescale_ai/solver/transient/{datapipe,rollout,train,inference}.py` — nodal `[N,T,Fo]` only

**Exit:** short design note in the PR (1 screen): data schema, head placement, loss, eval export.

---

## Phase 1 — Convert McLaren sparse nodal probes → global time series

**Problem:** `acceleration_t*` / `force_t*` / `moment_t*` / `rib_defl_t*` on the VTP are sparse overlays (almost all zeros). Mean-over-N training learns “predict zero.”

**Do (offline, dataset-side first):**

1. Freeze the probe list from `automation-ai-extractor/.../probe_map.json` + `scorecard_field_map.json` (~12 instruments: head/T1/T12/pelvis acc; 3 ribs; neck/pubic/shoulder/backplate/T12 load cells — expand components as needed, e.g. Fx/Fy/Fz or resultants per product decision).
2. Write a one-shot converter (script under `mclaren-crash-pole/scripts/`):
   - For each case: read VTP (or PSA CSV sidecars if cleaner) → extract nonzero probe histories.
   - Write **global time-series** into `case_data.yml` (or sibling `probe_timeseries.yml`) in the same shape FEA expects for `outvar_ts_keys` (per-base-name lists aligned to `displacement_t*` times).
   - Optionally strip sparse probe arrays from VTP to shrink I/O (keep `displacement_t*` + mesh).
3. Re-init / patch `versionMetadata` on a **smoke dataset** (1–2 cases, then 18):
   - Knobs → `globalVariables` **input** (unchanged)
   - Probe bases → `globalVariables` **output** time series
   - `displacement_*` → `nodeVariables` **output** only
4. Document the exact YAML schema + variable names in this folder (`docs/probe-global-schema.md` when frozen).

**Defer:** changing AI surface extraction tiles / metadata so new extracts emit globals natively (Phase B).

**Exit:** one smoke case where globals load as `[T, G]` without touching Transient code yet (reader unit test or small Python check).

---

## Phase 2 — Implement Transient GeoTransolver joint outputs (`rescale-ai` branch)

**Detailed mechanisms / NVIDIA+Guangchen rationale (review before coding):**  
→ [`geotransolver-global-ts-implementation-plan.md`](./geotransolver-global-ts-implementation-plan.md)

Work on `feat/transient-global-ts-outputs`. Mirror FEA semantics with Transient naming.

### 2a. Platform / config wiring

- `transient_model.py` `_collect_variables`:
  - Allow `globalVariables` with `type=output` and `_t*` names → dedupe to `outvar_ts_keys`
  - Keep rejecting **input** time-series globals (or support later; not needed for McLaren)
  - Pass `outvar_ts_keys` + `global_output_dim` into datapipe / model Hydra groups
- Config YAML: `datapipe.outvar_ts_keys`, model `global_output_dim`, optional `global_loss_weight`

### 2b. Datapipe

- Extend `SimSample` with `outvar_ts: Optional[Tensor]` → `[T, G]` (align timestep count with nodal `T`)
- Load from case YAML timeseries (same helper pattern as `solver/fea/datapipe.py`)
- Stats: `outvar_ts_mean` / `outvar_ts_std` (per-channel)
- Keep nodal path: `node_target` = displacement only (`Fo=3`), **not** sparse force channels

### 2c. Model / rollout (`GeoTransolverTimeConditional`)

- Keep nodal head: `[N, T, 3]` (or current time-conditional layout)
- Add **global decoder**: pool token / point latents → MLP → `[T, G]`  
  - Start with FEA-style **mean pool + MLP** (simplest, reviewable)  
  - Optional later: attention pool (TwoStream-inspired)
- Forward return: `(node_pred, global_pred)` when `global_output_dim > 0`

### 2d. Train / val loss

```text
L = L_disp(node_pred, node_target) + λ * L_probe(global_pred, outvar_ts)
```

- Default `λ` tunable (Guangchen’s GMI note: balancing node vs global loss matters)
- Log separate MSE_disp / MSE_probe (and per-probe if cheap)

### 2e. Inference / eval export

- Write predicted probe histories (JSON/CSV/yml) alongside predicted VTP displacement
- Do **not** require stuffing probes back into sparse nodal fields for v1
- Platform eval may stay displacement-heavy initially — document gap; smoke-check via local inference script

### 2f. Tests

- Unit: variable collection accepts global TS outputs; rejects only what we still disallow
- Unit: datapipe loads `outvar_ts` aligned to `T`
- Unit/GPU smoke: tiny synthetic mesh + `G` globals trains 1–2 steps without shape errors

**Exit:** CI green on new units; PR description points Guangchen at rollout + loss + schema.

---

## Phase 3 — Workstation test (EU HPS)

Workstation: current Grossular box (`udeprod_ZUKEb@52.17.146.218`) or successor.

1. Clone / update `rescale-ai` **on the branch**:
   ```bash
   git fetch origin
   git checkout feat/transient-global-ts-outputs
   # install / editable as you already do for train
   ```
2. Point at converted smoke dataset on HPS  
   (`mclaren-p35-side-pole-*` after Phase 1 conversion, or a new `…-global-ts-smoke`).
3. Create / reuse model version with:
   - Architecture: Transient · `geotransolver_time_conditional`
   - Enabled: knobs (inputs), `displacement` (node out), probe globals (global out)
   - Disabled: sparse nodal `force`/`moment`/`acceleration`/`rib_defl` if still present
4. Short train (epochs small, `num_workers=1` if memory tight).
5. Check:
   - Train starts (no “time-series globals not supported”)
   - TB / logs show both loss terms
   - Inference dumps probe curves with finite values (not all ~0)
   - Displacement VTP still sane
6. **Guangchen review:** send PR + 1 smoke plot (e.g. one force/acc channel GT vs pred) + loss curves.

**Exit:** “works” or “doesn’t” with a short failure note (shape / OOM / loss collapse / export gap).

---

## Phase B — Deferred: extractor / metadata tiles

After the branch proves training:

- AI extractor: emit probe histories as YAML global timeseries (not sparse VTP overlays)
- Optionally stop writing sparse `force_t*` etc. on mesh
- Metadata / `versionMetadata` defaults: knobs input; probes global output; displacement nodal output
- Re-extract or batch-convert the 18+ corpus

Not blocking Phase 2–3.

---

## Suggested order of work (checklist)

- [x] **0** Branch `feat/transient-global-ts-outputs` from `main`
- [x] **0** Design note (schema + head + loss) — `rescale_ai/solver/transient/GLOBAL_TS_OUTPUTS.md`
- [x] **1** Probe → global YAML converter + smoke case (`scratch/HFuKPb` → T=42, G=37)
- [x] **1** Document frozen probe / channel names — `docs/probe-global-schema.md`
- [x] **1** Workstation: convert `mclaren-p35-side-pole-19` all 18 cases → `timeseries` **T=41, G=39**; patch `versionMetadata` (39 global outputs; probe node fields disabled; displacement kept)
- [x] **2a** Transient variable collection + Hydra wiring
- [x] **2b** Datapipe `outvar_ts`
- [x] **2c** GeoTransolver global decoder
- [x] **2d** Joint loss + logging
- [x] **2e** Inference export of probe TS
- [x] **2f** Unit tests
- [ ] **3** Clone branch on workstation → train smoke → plots
- [ ] **3** Guangchen triple-check
- [ ] **B** Extractor tile change (later)

---

## Risks / watchouts

| Risk | Mitigation |
|------|------------|
| Timestep misalignment (disp vs probe) | Assert equal `T`; fail fast in datapipe |
| Loss dominated by displacement | Tunable `λ`; log split metrics |
| Pooling washes out crash localization | Start mean-pool; if probes weak, try attention / probe-token conditioning later |
| Platform eval still displacement-only | Local export script for Phase 3; file follow-up ticket for UI eval |
| Starter-18 too thin for real probe accuracy | Treat Phase 3 as **plumbing smoke**, not accuracy claim |
| OOM on 1.28M mesh | Same as today: low workers, time-conditional recipe already in use |

## Reference links (internal)

- Guangchen FEA MGN global TS: commit `a4a13dc08` · `solver/fea/rollout.py` (`global_output_dim`)
- Slack (GMI decoder working / loss balance): Forge thread ~2026-02-19
- Slack (McLaren: GeoTransolver needs extension for global TS): DST thread ~2026-06-23
- Probe map: `automation-ai-extractor/src/core/solvers/ls_dyna/probe_map.json`

## Decision already made

- **Primary architecture:** Transient GeoTransolver (not MGN).
- **Primary outputs:** nodal displacement + global probe time series.
- **Inputs:** existing numeric DOE knobs.
- **Sparse nodal probes:** migrate off the train targets (convert → globals).
