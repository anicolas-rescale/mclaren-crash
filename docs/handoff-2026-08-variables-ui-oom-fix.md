# Handoff — Variables / Cases UI OOM on large fea-deform workstations

**Status:** DONE — merged to `main`  
**Date:** 2026-08-14  
**PR:** https://github.com/rescale/rescale-ai/pull/1186  
**Merge commit:** `1ef12cbc5`  
**Branch:** `fix/variables-patch-api`  
**Severity was:** P0 (killed Training Workstations)

Related docs:

- [`variables-ui-oom-bugfix-plan.md`](./variables-ui-oom-bugfix-plan.md) — original diagnosis / plan  
- [`geotransolver-global-ts-implementation-plan.md`](./geotransolver-global-ts-implementation-plan.md) — **separate** next track (not blocked by this)

---

## One-liner

Flipping a Variables toggle (or opening Cases) on McLaren-scale `fea-deform` time-series datasets was **cannibalizing RAM** and killing ~10 workstations of various sizes. Train was never the trigger. Compact variables API + sparse PATCH + lazy cached case thumbs fixed it; PR is in `main`.

---

## What was actually dying

Dataset: `mclaren-p35-side-pole-19` (~14 GB, ~1600 flat global `*_t*` rows + nodal TS).

| Trigger | What went wrong |
|---------|-----------------|
| Open **Variables** / toggle a TS group | Fat `GET` + debounce **full PUT** of the entire variables document into React + **16 gunicorn workers** → thrash → OOM |
| Open **Cases** | Eager `GET /cases/{id}?nodeVariable=…` per row → **VTK thumbnail generation storm** → second OOM path |
| Bonus | Missing DQ payload crashed Variables; broken thumb URLs 404-retried → flicker |

Idle workers already multi‑GB. Available RAM could go ~54 Gi → ~0.6 Gi. SSH died. Felt like “the box randomly exploded.”

Until prod ships this build, the interim advice was: **don’t hammer Variables toggles on fat time-series datasets** without a patched WS.

---

## What we shipped

### Backend
- Compact `GET /variables` via `variables_for_api()` → scalars + `timeSeriesGlobalGroups` / `timeSeriesNodeGroups` (+ `memberNames`)
- `GET /variables/summary` for browse drawer (~hundreds of bytes)
- Sparse `PATCH /variables` (groups / named vars); no post-save full refetch
- On-disk YAML stays **expanded** for training compatibility
- PUT kept for legacy; compact PUT preserves on-disk TS

### Frontend
- Consume groups; training / Cases / preprocessing / refinement **expand** via `expandVariablesForTrainingConfig` where flat lists are still required
- Variables UI stays on compact payload (don’t re-inflate in the shared hook)
- `LazyCasePreview`: cached `.webp` only; resolve off-DOM with accel/displacement fallbacks; mesh on click
- `PreviewContainer`: stable fallbacks, no 404-retry flicker loop
- Null-safe `DataQualityWarning`
- Codex follow-ups: expand for preprocessing + refinement; clear `openWhenReady` on failed/no-mesh case link

### Live validation (WS `EQumX` / `LtuVLb`)
- Summary ~392 B, compact GET ~58 KB
- Toggle `timesteps` on/off → RAM stayed ~10 Gi used / ~49 Gi free
- Cases thumbs stable (no broken-icon loop)
- Training artifact creation did not tip the box

---

## Key files

| Area | Path |
|------|------|
| Compact / PATCH models + logic | `rescale_ai/data/datasets/dataset_version.py` |
| Routes | `server/app/routes/dataset_version_routes.py` |
| Variables hooks | `frontend/src/hooks/useDatasetVariables.ts`, `datasetVersions.ts` |
| Lazy thumbs | `frontend/src/components/Data/DatasetCases/LazyCasePreview.tsx` |
| Preview retries / fallbacks | `frontend/src/components/shared/PreviewContainer/index.tsx` |

Surgical WS patches (if anyone still needs a pre-prod box): historically under `mclaren-crash-pole/.ws-patch-backup/` — prefer waiting for a build that includes `#1186`.

---

## CI / merge notes

- Several `frontend_build/index.html` hash conflicts with `main` — **never pick a side**; merge then `cd frontend && npm run build` and commit artifacts
- One flaky PyVista segfault in `test_twostream_vtm_parity` (unrelated) — re-run was enough
- Codex reviewed; P1/P2 addressed before merge
- Team norm on this repo: self-merge after green CI is common; human tag optional

---

## What’s next (not this PR)

| Track | Notes |
|-------|--------|
| **Prod rollout** | Wait for AI Physics build that includes merge `1ef12cbc5` / PR 1186 |
| **GeoTransolver global TS outputs** | Separate design/impl on `feat/transient-global-ts-outputs` — synthetic fixtures first; HPS dataset + train artifacts already on storage |
| **Displacement thumbs** | Most cases only have `acceleration_t0.000000.webp`; UI falls back. Optional later: regenerate displacement thumbs offline |

---

## Handoff checklist

- [x] Root cause identified (Variables fat GET/PUT + Cases VTK storm)
- [x] Fix implemented and validated on McLaren dataset / live WS
- [x] PR opened, CI green, Codex notes addressed
- [x] Merged to `main` (2026-08-14)
- [ ] Confirm when the fix lands in a published workstation / desktop-dev build
- [ ] Resume GeoTransolver global-TS work when ready (new session)

**We’re done for this bug.** Next chat should start from GeoTransolver global TS or prod-build verification — not re-litigate Variables OOM unless something regresses after release.
