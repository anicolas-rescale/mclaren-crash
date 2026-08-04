# Handoff — McLaren ES-2 side-pole + LS-DYNA extractors

**Date:** 2026-08-03  
**Local path:** `/Users/anicolas/Documents/rescale-projects/mclaren-crash-pole`  
**Remote:** https://github.com/anicolas-rescale/mclaren-crash

## Status

- Extractor work lives in open PRs (merge when reviewed):
  - AI: https://github.com/rescale/automation-ai-extractor/pull/17
  - Metadata: https://github.com/rescale/automation-metadata-extractor/pull/25
- This repo: scorecard pointer docs, scratch/ gitignored, DOE example under `examples/lsdyna-doe.json`.
- Local GT job artifacts: `scratch/HFuKPb/` (not committed).

## How to run extractors on a Utilities / LS-DYNA job

1. Upload/sync job results (d3plot + PSA CSVs / `results.json` as available).
2. Copy `examples/lsdyna-doe.json` → job root as `lsdyna-doe.json`.
3. Optional: `export AUTOMATION_ANALYSIS=ls_dyna` in command/env panel.
4. AI tile: leave `FRAME_POLICY=all` for full transient + auto probes.
5. Metadata tile: `mclaren_knobs` Inputs + PSA Findings when present.

## Related

- Xerox nip sample/handoff: sibling folder `xerox-contact-nip` (separate repo).
- Packaged probe/scorecard maps: `automation-ai-extractor` `src/core/solvers/ls_dyna/`.
