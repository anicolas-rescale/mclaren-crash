# Handoff — Transient GeoTransolver global time-series outputs

**Date:** 2026-08-18
**Repos:** `rescale-ai` branch `feat/transient-global-ts-outputs`; experiment notes in `mclaren-crash-pole`
**Audience:** next Claude / Andy continuing this work; Guangchen reviews the PR

---

## TL;DR

Plumbing is in and smoked. PR for Guangchen:
https://github.com/rescale/rescale-ai/pull/1217
(`feat/transient-global-ts-outputs`). Do **not** sell McLaren numbers as
accuracy. 18 OFAT cases + mean-pool cannot teach door-inner intrusion
(`KwXUX` last-frame disp L2 still ~42% at epoch 200).

`.claude` is gitignored in `rescale-ai`. This file is local agent memory.
Committed reviewer notes: `rescale_ai/solver/transient/GLOBAL_TS_OUTPUTS.md`.

---

## What merged into the branch

Port FEA MGN `outvar_ts` onto `GeoTransolverTimeConditional`:

- `rescale_ai/solver/transient/global_decoder.py` — `call_geotransolver_with_hidden`,
  `replay_geotransolver_with_hidden`, `TransientGlobalDecoder` (mean-pool + MLP)
- `rollout.py` — joint nodal + global return when `global_output_dim > 0`
- `datapipe.py` — YAML timeseries load, `outvar_ts` stats, T alignment
- `train.py` — `L_disp + λ L_probe`, TB `loss/disp` / `loss/probe`
- `inference.py` — `*_global_values.json` next to VTPs
- `file_utils.py` — skip clock keys `timesteps` / `times` / `frame_indices` /
  `vtp_array_names` when expanding YAML timeseries into Variables
- Tests: `tests/rescale_ai/solver/transient/test_global_ts.py`,
  `test_rollout.py` global shapes, `tests/unit/test_version_metadata_defaults.py`

**Do not commit** workstation Hydra yamls
(`mclaren_holdout_p35.yaml`, `mclaren_smoke8k.yaml`) — they have
`/enc/udeprod_cXBNn/...` paths.

---

## Guangchen’s review points (done vs not)

| Ask | Status |
|-----|--------|
| v1 = mean-pool + MLP | Done. `aggregation="mean"` |
| Latent = after GALE, before `ln_mlp_out` | Done |
| Prefer `forward_features()` in PhysicsNeMo | **Not done** — we do not own the tile package |
| Smaller OK: `return_hidden_states=True` | Used if present; NVIDIA main name `return_point_features` preferred |
| No forward hooks | Replay walks modules; not `register_forward_hook` |
| Do not use `return_embedding_states` | Tests assert this |
| Modular aggregation for later attention | `TransientGlobalDecoder.aggregate()`; `attention` raises `NotImplementedError` |

Tile PhysicsNeMo **2.1.0a0** has neither latent flag, so Grossular uses the
replay path. That is the main architecture question on the PR.

---

## McLaren experiment (`cXBNn`)

- Job `cXBNn`, EU, Grossular / g5.4xlarge, 1× A10G. SSH was
  `udeprod_cXBNn@54.154.10.195` (timed out 2026-08-18 late afternoon).
- Overlay: `/enc/udeprod_cXBNn/work/rescale-ai`
- Dataset: `mclaren-p35-side-pole-18-probes` on HPS `/enc/udeprod.fNLMWb/work`
- Tag `crashPostProcOK`, 18 extracts. Collect regexes must be **anchored**
  (`^case_data\.yml$`) or empty `.lock` files fail verification.
- Init: overlay `file_utils` so clock keys are not Variables groups.
  Displacement 41 frames `t0.000`…`t0.080`. YAML T=42 with duplicate last
  clock; train truncates probes to T=41.
- Decimate `--target-points 20000` → ~16k pts. Copy `case_data.yml` into
  preprocessed dirs so probes load. Full mesh ~1.26M will not fit A10G.
- Do **not** open Variables UI on that box (OOM history).
- `RESCALE_AI_DISABLE_POST_TRAINING=1` — CLI `train.py` atexit crashes
  without platform model metadata.
- Kill ollama before train (~15 GB VRAM).

**Knobs (10):** door inner/outer, ttf, airbag E22 / z-up, bracket_cutt,
brace_P16, cavity_foam, rail_foam, seat_inb_foam.
Dropped `trim_woodfibre` (0 on all 18, including the woodfibre doortrim case).

**Outputs:** nodal displacement only; 28 globals (head acc xyz; neck upper F/M
xyz; T1/T12 acc xyz; rib defl + VC U/M/L; shoulder left force xyz; pelvis acc
xyz; pubic Fy). Not in the 28: backplate F/M, T12 LC (Fz/Mz missing in CSVs —
do not zero-fill), pubic Fx/Fz.

**Holdouts (do not hold unique-knob-only cases):**

| Case | Job | Parent | Reason |
|------|-----|--------|--------|
| `case8_KwXUX` | KwXUX | gfkFPb | door inner 1.3 mm only |
| `case14_dWNQX` | dWNQX | OUjFPb | cavity foam 60 gl only |

1.3 mm and 60 gl still in train as combos (`vkDMX`, `WLNQX`, `Wbnuib`).
Do **not** hold `HtscV` (TTF 9 ms unique) or `Pbnuib` (rail foam unique).

Helpers: `mclaren-crash-pole/scripts/ws_p35_probes/`
Notebook: `mclaren-crash-pole/notebooks/cXBNn_collect_init_validate.ipynb`
Eval on box: `/enc/udeprod_cXBNn/mclaren_holdout_c9_c3/eval/epoch_{010,050,100,200}/`

Holdout 28-channel grids:
- Epoch 10: `docs/geotransolver-holdout-clean-2026-08/plots/epoch_10/`
- Epoch 200 (Desktop screenshots, also on PR 1217):
  `docs/geotransolver-holdout-clean-2026-08/plots/epoch_200/`

---

## Metrics (physical units; disp = mm)

| Epoch | probe MSE train / hold | disp RMSE train / hold | last-frame disp rel L2 train / hold |
|------:|-----------------------:|-----------------------:|------------------------------------:|
| 10 | 7.85 / 5.15 | 24.4 / 27.3 | 21% / 31% |
| 50 | 5.63 / **3.43** | 21.6 / 24.7 | 19% / 30% |
| 100 | 4.43 / 4.27 | 22.6 / 25.7 | 19% / 30% |
| 200 | **3.28** / 4.27 | **20.2** / **23.7** | 19% / **30%** |

Holdouts at 200: `dWNQX` probe 2.95 / disp 18.6 / L2 **17%**; `KwXUX` probe
5.59 / disp 28.9 / L2 **42%**.

Train outlier `case11_hEvTfb` (brace Al): probe MSE ~29 → ~4.0.

Last-frame mean GT disp mag on this mesh is ~300–350 mm (older dump case0
~349 mm). RMSE ~24 mm is **millimetres**, not percent; it averages easy
early frames and far-field nodes. Rel L2 30% hold is the crush-zone metric
and is basically `mean(17%, 42%)`.

Staged cosine restarts put epoch 200 at LR `1e-4`; train loss ~0.17 vs
**~0.08 around epoch 190**.

**Prior 39-channel holdout numbers are poisoned** (flat-zero / mis-mapped
globals). Ignore `docs/geotransolver-holdout-2026-08/` for probe accuracy.

---

## If displacement stays weak

1. More cases, especially door-inner combos / a small DOE — not more OFAT uniques.
2. Door thickness is a **global scalar**, not a remeshed shell field.
3. Loss: weight late frames and/or high-disp / impact-side nodes; maybe lower `λ`.
4. Do not stage-restart cosine for “best epoch 200”.
5. ROI-denser mesh, not uniform 16k.
6. Attention-pool / probe tokens help **globals**, not `KwXUX` 42% disp.

---

## Do not

- Hold unique-knob-only cases
- Open Variables UI on the A10G box
- Enable T12 LC Fz/Mz (missing)
- Treat old 39-channel holdout probe numbers as clean
- Commit workstation Hydra yamls
- Force-push `main`

---

## PR

Opened and requested review from `guangchen-rescale`:
https://github.com/rescale/rescale-ai/pull/1217

Merged `main` into the branch (no rebase). Epoch-200 holdout 28-channel
grids are in the PR body (`KwXUX`, `dWNQX`) from Desktop screenshots after
SSH to `54.154.10.195` timed out. Metrics table is 10/50/100/200.
