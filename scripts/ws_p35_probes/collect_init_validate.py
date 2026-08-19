#!/usr/bin/env python3
"""collect_cases → initialize_dataset → validate_dataset on tag crashPostProcOK.

Run on workstation cXBNn with overlay PYTHONPATH:

  source /program/rescale-ai-2.1.6/venv/bin/activate
  export PYTHONPATH=/enc/udeprod_cXBNn/work/rescale-ai:$PYTHONPATH
  python collect_init_validate.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    DATASET_NAME,
    EXPECTED_JOB_IDS,
    FILE_PATTERNS,
    NUM_WORKERS_COLLECT,
    NUM_WORKERS_INIT,
    TAG,
)


def _job_id(job) -> str:
    return getattr(job, "job_id", None) or job._initial_data.get("id", "")


def main() -> int:
    from rescale_ai.interactive import DatasetBuilder

    builder = DatasetBuilder()
    print(f"HPS link_path={builder.hps.link_path}", flush=True)

    jobs = builder.search_jobs(tag=TAG, limit=100)
    found = {_job_id(j): j for j in jobs}
    print(f"tag={TAG!r} found={len(found)} expected={len(EXPECTED_JOB_IDS)}", flush=True)
    missing = [jid for jid in EXPECTED_JOB_IDS if jid not in found]
    extra = sorted(set(found) - set(EXPECTED_JOB_IDS))
    if missing:
        print(f"WARNING missing tagged jobs: {missing}", flush=True)
        print("Fetching missing IDs directly...", flush=True)
        fetched = builder.job_explorer.get_by_ids(missing)
        for j in fetched:
            found[_job_id(j)] = j
        still = [jid for jid in EXPECTED_JOB_IDS if jid not in found]
        if still:
            print(f"ERROR still missing: {still}", flush=True)
            return 1
    if extra:
        print(f"NOTE extra tagged jobs (ignored): {extra}", flush=True)

    ordered = [found[jid] for jid in EXPECTED_JOB_IDS]
    builder.last_jobs = ordered
    print("jobs:", [(_job_id(j), getattr(j, "name", "")[:80]) for j in ordered], flush=True)

    scratch = builder.collect_cases(
        name=DATASET_NAME,
        jobs=ordered,
        file_patterns=FILE_PATTERNS,
        num_workers=NUM_WORKERS_COLLECT,
        verbose=True,
    )
    print(f"scratch={scratch}", flush=True)

    builder.initialize_dataset(
        name=DATASET_NAME,
        dataset_type="fea-deform",
        surface_file_name="case_data.vtp",
        num_workers=NUM_WORKERS_INIT,
    )

    final = builder.validate_dataset(
        DATASET_NAME,
        num_workers=NUM_WORKERS_INIT,
        upload_to_platform=True,
        description=(
            "McLaren P35 ES2 side-pole, 18 OFAT extracts (crashPostProcOK), "
            "displacement nodal + occupant probe global time series"
        ),
    )
    print(f"dataset={final}", flush=True)

    cases_dir = Path(final) / "cases"
    summary = {
        "dataset_name": DATASET_NAME,
        "dataset_path": str(final),
        "n_cases": len(list(cases_dir.glob("case*"))) if cases_dir.is_dir() else 0,
        "job_ids": EXPECTED_JOB_IDS,
        "tag": TAG,
    }
    out = Path(final).parent.parent / "work" / "mclaren_p35_probes" / "collect_summary.json"
    # HPS is storage_wtaTdb; write next to dataset too
    alt = Path(final) / "collect_summary.json"
    alt.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    print("DONE collect_init_validate", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
