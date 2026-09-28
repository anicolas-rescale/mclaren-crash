# Handoff — McLaren P35 UI-only end-to-end walkthrough (Sep 2–3, 2026)

**Date:** 2026-09-02 Wed evening → 2026-09-03 Thu morning  
**Updated:** 2026-09-28 (customer share follow-up)  
**Goal:** Full UI workflow for Transient GeoTransolver with global TS probes — no CLI, no platform SDK, pure webapp clicks  
**Outcome:** **Training succeeded** after overnight retry. **Evaluation completed**. Global TS data exists, plots render in UI. **Inference fundamentally broken** — UI sliders are decorative (frontend/backend disconnected), requires SSH to manually copy missing metadata files.  
**Verdict:** UI path is **barely viable** with multiple sharp edges; production users would hit **5+ blocking issues** without SSH access or internal tile knowledge. **Inference is completely non-functional via UI-only path** for models with global features.

**Customer PDF:** [`McLaren AI Physics walkthrough.pdf`](./McLaren%20AI%20Physics%20walkthrough.pdf) (same flow, written for Roberto / Sumit). DOE: [`../examples/lsdyna-doe.json`](../examples/lsdyna-doe.json).

---

## Customer share / access (Sep 25–28)

Shared the walkthrough PDF + HPS link with **Roberto Cepeda** and **Sumit Sharma** (cc Dinal, James) after the Sep 25 readout.

**Sep 28 — Roberto reply:** PDF links and the `*.json` did not open for him. Asked to get the links and json by email.

**What that likely means:** without folder/job access he cannot finish the walkthrough. The extract DOE also sits on every AI Physics extract job, so a failed json download from Drive-style links is a strong signal he cannot see those jobs yet.

**Where the jobs live:** Rescale DST folder **`Side_Pole_Data_Occupant`** (shared with Andy, not owned by Andy). Contains:
- original McLaren Passive Safety Automation runs
- post-processing / AI Physics extract jobs (tag `crashPostProcOK` / related)

**Ask:** if Roberto / Sumit still cannot see that folder or those jobs, **James shares `Side_Pole_Data_Occupant`** with them. Andy emailed the DOE as `lsdyna-doe.json` attachment and pointed them at that folder.

**PDF note for them:** a couple of broken links were Google Doc comments about versioning. They no longer apply to the latest AI Physics platform. Safe to ignore. Do not rely on the Google Doc itself for external share.

Thread: [McLaren AI Physics walkthrough and HPS access](https://mail.google.com/mail/u/#inbox/1a0d961c4986b667). HPS (optional toy path): https://eu.rescale.com/storage/wtaTdb/status/ (McLaren HPS on Rescale DST).

---

## What we were testing

End-to-end AI Physics workflow for McLaren P35 side-pole crash FEA:
- **Dataset:** 18 cases (16 train DOE + 2 named holdouts: `case3_dWNQX`, `case9_KwXUX`)
- **Model:** Transient · GeoTransolver time-conditional, 200 epochs
- **Outputs:** Nodal displacement + 28 global time-series probe channels (occupant injury metrics)
- **Platform:** Internal/Dev tile (`rescale-ai-physics_e2e_desktop-dev`) on workspace `udeprod_GYyPfb@3.253.111.193`
- **Constraint:** Zero CLI except emergency SSH debugging; all actions via UI

---

## Timeline & blockers

### Wed evening: Dataset + split creation

**Blocker 1: Platform dataset exists but not visible in workspace**
- HPS `fNLMWb` attached to **two** workspaces (`udeprod_KLvYU` [old 2.1.8] + `udeprod_GYyPfb` [new 2.1.10])
- Dataset `mclaren-p35-side-pole-andy` (platform ID `Bwuia`, local `317ded25...`) already collected on old box
- New workspace UI showed "no datasets" until **manual SSH refresh** of `/enc/udeprod.fNLMWb/work/datasets/`
- **Workaround:** Multi-attach HPS worked; just needed to wait/refresh

**Blocker 2: Create Version for train/test split silently rejects empty filter**
- Tried: **Dedicated train/test** → select 16 train cases + 2 test → no explicit "Create Version" UX
- UI only creates versions via:
  - **Metrics** (runs postprocess + creates version)
  - **Mesh Processing** (decimation/smoothing → new version)
- **Workaround:** Created **v1 `training`** (exclude holdouts via filter `case_path NOT case3_dWNQX case9_KwXUX`), **v2 `testing`** (include only holdouts)
- Metrics job ran in background (`defer_heavy_processing=True` → postprocess pool child)

**Blocker 3: Metrics "thinking" spinner never clears in UI**
- Create Version with Metrics shows `metricsPending: true` → background job runs
- UI spinner stayed for ~15+ min even after job finished
- **Root cause:** Postprocess reads full VTPs (~650 MB each × 16 cases) via `ProcessPoolExecutor(max_workers=1)` per gunicorn worker
- SSH showed `metricsPending: false` on disk while UI still showed spinner
- **Workaround:** Refresh browser / wait longer; data was actually ready

### Wed ~10 PM: Decimation (mesh reduction for fast train)

**Context:** Full meshes ~1.2M verts/case → need ~16k/case for reasonable train time (prior `cXBNn` run used CLI `decimate_dataset`)

**Blocker 4: UI Mesh Decimation defaults are wrong**
- UI offers **MGN Decimation** (banner: "200k–400k points recommended")
- Actual target: **To N Points → 20000** (buried in a dropdown)
- First attempt: clicked default → **v4 created with only triangulate, no decimation** (metadata `targetPoints: None`, ops `['triangulate']`)
- **Workaround:** Redo on **v2 testing** → explicitly select "To N Points", type `20000`, Apply

**Blocker 5: UI Apply → 504 Gateway Timeout (misleading failure)**
- Submit decimation for **v1 training** (16 cases) → 504 error in browser after ~30 sec
- **Reality:** Job kept running in background; ~7.6 min later, **v3 `training decimated`** appeared (~256k verts total, ~16k/case)
- Same for **v5 testing** redo: 504 in UI, but job finished (~3.5 min, 2 cases)
- **Root cause:** Decimation uses `asyncio` + long VTP reads; nginx times out while job proceeds
- **Workaround:** Ignore 504; poll versions list or SSH to confirm completion

### Wed ~11 PM – Thu ~4 AM: Training submission & overnight run

**Blocker 6: License rejection on Internal/Dev tile**
- Created model `myCool_SidePoleCrash_GeoTransolver_model` → train v3 / test v5 / GeoT / 200 epochs
- Submit → **immediate failure:** `"Not authorized to use the on-demand license from Rescale"`
- Draft job `dTKyib` used software code `rescale-ai-physics-dev`
- **Root cause:** Dev tile doesn't have AI Physics on-demand license for `anicolas+mcl` account
- **Workaround:** Unknown to user; overnight **retry succeeded** (possibly different tile/config or license provisioned)

**Success:** Retried model `myCool_decimated_SidePoleCrash_GeoT` launched overnight
- Job **RqRMX** on Grossular (1× A10G assumed)
- Train: **~5.2 h** (200 epochs, ~93 sec/epoch)
- Eval: **~35 min** (17 cases: 14 train + 1 val + 2 test)
- Status: **Completed** by ~12:20 UTC (5:20 AM local)
- Avg loss ~0.011 at epoch 200
- Headline R²: mean **-0.20** / median **0.87** (skewed by some bad timesteps/channels)

### Thu ~5 AM: Evaluation artifacts & inference attempt

**Blocker 7: Global TS plots not obvious in UI**
- User asked: "where do I see the global time series plot?"
- Eval writes **JSON files** per case: `prediction_case3_dWNQX_global_values.json` with arrays like:
  - `time_step`, `head_acceleration_x`, `head_acceleration_x_pred`, ...
- No auto-generated line plots during eval (only displacement residual heatmaps/histograms)
- **Reality:** PR #1234 added `time_step` field **for the 2D viewer in UI**, not automatic plot export
- **Workaround:** User found the **"Global Outputs"** tab in Evaluation UI (renders plots from JSON)

**Blocker 8: Inference fails with CUDA import error (first attempt)**
- Tried inference on default settings → **error:** `"cudart shared object not found"`
- Model class `GeoTransolverTimeConditional` exists but requires CUDA libs to instantiate
- **Root cause:** Inference job defaulted to CPU-only node; GeoTransolver needs GPU
- **Workaround:** User launched Grossular (GPU) workspace

**Blocker 9: Inference fails with "case_data.yml not found" (second attempt, on GPU)**
- Launched new Grossular workstation `udeprod_OUPNn@54.229.48.74`
- UI showed inference tab with **10 global input sliders** (airbag_E22, door_inner_mm, cavity_foam_gl, etc.)
- Clicked "Run Inference" without changing sliders
- **Error:** `FileNotFoundError: case_data.yml not found in /tmp/transient_inference_*/case`
- **Root cause (triple failure):**
  1. **Decimation doesn't copy `case_data.yml` to preprocessed directory** — only copies decimated VTP mesh
  2. **Inference backend still expects file-based `case_data.yml`** with both global inputs AND the list of 28 output channel names
  3. **Inference UI sliders are decorative** — they collect values but backend never receives them; backend ignores sliders completely and tries to read the missing file
- **Reality check:** SSH revealed preprocessed test cases had only `case_data.vtp` (decimated mesh), no `case_data.yml` (metadata). Original `case_data.yml` exists in raw `/cases/` directory but was never copied during decimation.
- **Workaround:** Manually copied `case_data.yml` from raw cases to preprocessed directories via SSH:
  ```bash
  cp .../cases/case3_dWNQX/case_data.yml .../preprocessed/vb3205392/case3_dWNQX/
  cp .../cases/case9_KwXUX/case_data.yml .../preprocessed/vb3205392/case9_KwXUX/
  ```
- **Follow-up (what inference history revealed):** the UI’s default inference request stages only the example mesh VTP (`artifacts/example_training_case/case.vtp`) into the per-request temp folder; it does not stage `case_data.yml`, so `CrashPointCloudDataset` can’t infer `outvar_ts_keys`.
- **Workaround (what we did):** copied a working `case_data.yml` (from `cases/case16_SbCgV/case_data.yml`) into `versions/0/artifacts/example_training_case/case_data.yml`, then inference can proceed.
- **Alternative fix:** make the UI upload/generate `case_data.yml` (from sliders + required `timeseries:` keys) or copy it alongside the mesh when building the request temp folder.
- **User confusion (justified):** "I see the yml is literally the whole list of inputs... I thought I was making those inputs by toggling the knobs and hitting run... wtf?"
- **Verdict:** Inference UI is **fundamentally broken** for models with global features. The UI shows input controls but they don't actually do anything. UI and backend are not connected.

**Where `case_data.yml` actually comes from (for the record — not a user error):**
- Pipeline is `collect_cases → initialize_dataset(dataset_type="fea-deform") → validate_dataset`
- **`collect_cases`** reads numeric DOE custom fields (knobs) from Rescale job metadata and **writes `case_data.yml`** next to `case_data.vtp`/`case_data.stl` for every raw case — this happened correctly for all 18 cases at original collection time
- **`initialize_dataset`** promotes those YAML scalars → `versionMetadata.yaml` globalVariables, and expands `timeseries:` → `_t*` global output entries for the UI
- Confirmed via SSH: all raw `cases/*/case_data.yml` files were intact (42KB, full knobs + 28 probe timeseries) — **the user did nothing wrong during collection**
- The file is dropped **twice downstream**, both bugs, neither user-facing:
  1. **Decimation** copies `case_data.vtp` to the preprocessed dir but not the sibling `case_data.yml`
  2. **Model's bundled inference example** (`artifacts/example_training_case/`) ships `case.vtp` + a thinner `case.yaml` (knobs only, no `timeseries:`) — never includes the real `case_data.yml`
- **Fix owners:** decimation/preprocessing pipeline (bug 1) + model inference-example packaging (bug 2). Neither requires user action once fixed.

---

## What actually worked (eventual happy path)

1. **Dataset collect:** Already done via prior CLI
2. **Train/test split:** Create Version with case filters → v1 training (16), v2 testing (2)
3. **Decimation:** Mesh Processing → "To N Points" → 20000 → Apply (ignore 504) → v3 train decimated, v5 test decimated
4. **Model create + train:** Select v3/v5, Transient GeoT, 200 epochs, 10 global knobs ON, nodal displacement ON, 28 global TS outputs → Submit
   - (Failed first time on license; retry overnight succeeded)
5. **Evaluation:** Auto-ran after training; wrote VTPs + global JSONs
6. **View results:** Evaluation tab → displacement plots + "Global Outputs" tab for probe curves
7. **Inference:** (partially blocked) Need to:
   - Select GPU hardware explicitly (Grossular)
   - Manually copy `case_data.yml` to preprocessed directories via SSH (UI sliders don't work)

---

## Bugs / UX debt for product team

### P0 (blocks non-expert users)

1. **Inference UI sliders are non-functional (models with global features)**  
   - UI shows sliders for global input features (knobs) but values are never sent to backend
   - Backend expects file-based `case_data.yml` with global inputs + output channel names
   - Decimation doesn't copy `case_data.yml` from raw cases to preprocessed directory
   - Result: **inference completely non-functional via UI-only path** for GeoTransolver/models with global features
   - User quote: "I see the yml is literally the whole list of inputs... I thought I was making those inputs by toggling the knobs and hitting run... wtf?"
   - **Fix:** Either (a) have decimation copy `case_data.yml` to preprocessed dir, OR (b) inference UI needs to generate `case_data.yml` from slider values before submitting job

2. **504 on long operations misleads users into thinking job failed**  
   - Decimation, metrics postprocess can run 5–10+ min; nginx times out at ~60s
   - User thinks "error" but job completes successfully in background
   - **Fix:** WebSocket progress updates or `202 Accepted` + polling UI

3. **License error has no self-serve recovery**  
   - "Not authorized to use on-demand license" → dead end for user
   - No indication of which tile/software has the license or how to request
   - **Fix:** Check license entitlement before showing software in tile dropdown, or show self-serve request flow

4. **Default decimation settings are wrong for ML training**  
   - Banner says "200k–400k for MGN" but GeoT needs ~16k/case
   - "To N Points" option buried; easy to miss
   - **Fix:** Add "recommended for training" preset or per-architecture hint

### P1 (sharp edges, workarounds exist)

5. **Metrics postprocess "thinking" spinner never updates**  
   - Version created but UI shows pending indefinitely
   - Postprocess finishes on backend but UI doesn't poll or SSE update
   - **Fix:** Poll `metricsPending` field or SSE event on completion

6. **Dataset not visible in new workspace after HPS multi-attach**  
   - HPS attach works but dataset list doesn't auto-refresh
   - **Fix:** Backend should trigger dataset rescan on HPS attach, or UI should auto-refresh

7. **Inference hardware defaults to CPU for GPU-only models**  
   - GeoT/MGN models fail on CPU with cryptic CUDA errors
   - No upfront validation or hardware selector in simple inference flow
   - **Fix:** Check model arch requirements and pre-select GPU, or block submission with clear error

### P2 (papercuts)

8. **No train/test version creation from Dedicated split UI**  
   - User selects 16 train + 2 test in Dedicated tab but no "Create Versions" button
   - Must use Metrics or Mesh Processing as side effect
   - **Fix:** Add explicit "Save as Train/Test Versions" action in Dedicated tab

9. **Global TS plots require finding hidden UI tab (Evaluation)**  
   - Data exists in JSON but user didn't know where to look
   - Displacement plots are obvious; global outputs tab is not
   - **Fix:** Surface "Global Outputs" tab prominently if model has `global_output_dim > 0`

10. **Inference UI lists global time series as scalars, not plots**  
   - Evaluation has "Global Outputs" tab with rendered time series plots
   - Inference writes same `*_global_values.json` format but UI only shows individual scalar values per timestep
   - **Fix:** Add same 2D viewer / plotting component to inference output tab (parity with evaluation)

---

## Recommendations for doc/training

**For customer-facing docs (AI Physics quickstart):**
- Add warning: "Mesh decimation may show 504 error; check Versions list after ~5 min to confirm completion"
- Show screenshot of "To N Points" decimation option (not default MGN banner)
- Mention Evaluation → Global Outputs tab explicitly for probe/scalar time series
- Note: "Inference output currently lists global time series as individual scalars; download the `*_global_values.json` to plot full curves"

**For internal runbooks:**
- Add troubleshooting: "License error on dev tile → retry or use prod tile"
- Document HPS multi-attach: "Dataset may not appear until workspace restart or manual SSH refresh"
- Note: "Inference requires GPU hardware for GeoTransolver/MGN models"

**For PMs/designers:**
- Consider "training mode" preset for decimation (16k–20k pts/case, not 200k–400k)
- Add progress bar or log tail for long-running version ops (metrics, decimation)
- Surface global TS outputs more prominently if present

---

## Artifacts from this run

**Workspace:** `udeprod_GYyPfb@3.253.111.193` (Internal/Dev tile, rescale-ai 2.1.10)  
**HPS:** `fNLMWb`  
**Dataset:** `mclaren-p35-side-pole-andy` (platform `Bwuia`, local `317ded25-18fa-436e-a393-10e135cf772d`)  
**Versions:**
- v0: Initial import (22.8M verts)
- v1: `training` — 16 cases, full res (20.2M verts)
- v2: `testing` — 2 cases, full res (2.5M verts)
- v3: `training decimated` — 16 cases, ~16k pts/case (~256k total) ✅ use this
- v4: `Testing decimated` — bad (triangulate only, ignore)
- v5: `testing decimation` — 2 cases, ~16k pts/case (~32k total) ✅ use this

**Model:** `myCool_decimated_SidePoleCrash_GeoT` v0  
**Job:** `RqRMX` (Grossular, A10G)  
**Config:** Transient · GeoTransolver time-conditional · 200 epochs · `global_loss_weight: 1.0` · 10 knobs + 28 global TS outputs + nodal displacement  
**Status:** Completed  
**Eval:** 14 train + 1 val + 2 test; displacement + global JSON files present  
**Holdouts:** `case3_dWNQX` (cavity_foam 60 / door_inner 1.2), `case9_KwXUX` (door_inner 1.3)

**Next steps (user's homework):**
- Try inference again on Grossular (now that `case_data.yml` is manually copied to preprocessed dirs)
- Verify global TS plots render correctly in inference output
- Compare holdout probe curves (eval vs inference) for sanity

**SSH fix applied (Thu 9:00 AM):**
- Manually copied `case_data.yml` from raw cases to preprocessed directories:
  - `case3_dWNQX`: `airbag_E22=0.0`, `cavity_foam_gl=60.0`, `door_inner_mm=1.2`
  - `case9_KwXUX`: `cavity_foam_gl=0.0`, `door_inner_mm=1.3`
- This unblocks inference but proves UI path is broken (sliders don't work)

---

## Bottom line for exec summary

**UI-only workflow is possible but fragile.** A determined user with SSH access and internal tile knowledge can complete train → eval → inference, but a **customer would hit 5+ blocking errors**:
1. Inference sliders don't work (frontend/backend disconnected)
2. 504 timeouts (looks like failure, actually success)
3. License rejection (no self-serve fix)
4. Wrong decimation defaults (trains on 200k pts → OOM or slow)
5. Inference CUDA error (no hardware selector)

**Short-term fix priority:**
1. **Inference slider → backend plumbing** (unblocks inference completely) OR decimation copies `case_data.yml`
2. 504 → progress UI or 202 + poll (unblocks decimation confusion)
3. License check upfront (unblocks dev tile submissions)
4. Decimation preset for training (prevents bad defaults)

**Long-term:** treat AI Physics as **early beta** for UI-only users; CLI + platform SDK remains the "real" path for now.
