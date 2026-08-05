#!/usr/bin/env python3
"""Export PSA catalog Inputs from clonedFrom parent → mclaren_catalog.json.

Utilities post-proc clones keep ``clonedFrom`` (e.g. aMYNZb → HFuKPb) but do
**not** copy Inputs custom fields. Metadata can still resolve DOE knobs if this
file is present on disk.

Env (set automatically on Rescale jobs):
  RESCALE_JOB_ID, RESCALE_API_KEY, RESCALE_API_BASE_URL (default https://eu.rescale.com)

Optional:
  SOURCE_JOB_ID — override parent (when clonedFrom is missing)
  MCLAREN_CATALOG_OUT — output path (default ./mclaren_catalog.json)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

CATALOG_KEYS = (
    "Door Inner",
    "Door Outer",
    "TTF",
    "Airbag",
    "Airbag Bracket",
    "Door Trim",
    "Door Brace",
    "Cavity Foam",
    "Foam Block",
    "Seat Variable",
    "Seat",
    "Description",
    "Door Variable",
    "Dummy",
)


def _api_get(base: str, path: str, token: str) -> Dict[str, Any]:
    url = f"{base.rstrip('/')}{path}"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Token {token}", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _catalog_from_custom_fields(cf: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name, info in cf.items():
        if name not in CATALOG_KEYS:
            continue
        if isinstance(info, dict):
            val = info.get("value")
        else:
            val = info
        if val is not None:
            out[name] = val
    return out


def resolve_source_job_id(base: str, token: str, job_id: str) -> Optional[str]:
    override = os.getenv("SOURCE_JOB_ID", "").strip()
    if override:
        return override
    job = _api_get(base, f"/api/v2/jobs/{job_id}/", token)
    parent = job.get("clonedFrom")
    if parent:
        return str(parent)
    return None


def main() -> int:
    job_id = os.getenv("RESCALE_JOB_ID", "").strip()
    token = os.getenv("RESCALE_API_KEY", "").strip()
    base = os.getenv("RESCALE_API_BASE_URL", "https://eu.rescale.com").strip()
    out_path = Path(os.getenv("MCLAREN_CATALOG_OUT", "mclaren_catalog.json"))

    if out_path.is_file() and out_path.stat().st_size > 2:
        print(f"[export_catalog] already present: {out_path}", flush=True)
        return 0

    if not job_id or not token:
        print(
            "[export_catalog] missing RESCALE_JOB_ID / RESCALE_API_KEY — skip",
            file=sys.stderr,
            flush=True,
        )
        return 0

    try:
        # Prefer catalog already on this job (true Duplicate that retained fields)
        own = _catalog_from_custom_fields(
            _api_get(base, f"/api/v2/jobs/{job_id}/custom-fields/", token)
        )
        if len(own) >= 3:
            catalog = own
            print(f"[export_catalog] using Inputs on current job {job_id}", flush=True)
        else:
            source = resolve_source_job_id(base, token, job_id)
            if not source:
                print(
                    "[export_catalog] no clonedFrom / SOURCE_JOB_ID — cannot fetch catalog",
                    file=sys.stderr,
                    flush=True,
                )
                return 1
            catalog = _catalog_from_custom_fields(
                _api_get(base, f"/api/v2/jobs/{source}/custom-fields/", token)
            )
            print(
                f"[export_catalog] fetched {len(catalog)} fields from parent {source}",
                flush=True,
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        print(f"[export_catalog] HTTP {exc.code}: {body}", file=sys.stderr, flush=True)
        return 1
    except Exception as exc:
        print(f"[export_catalog] failed: {exc}", file=sys.stderr, flush=True)
        return 1

    if not catalog:
        print("[export_catalog] parent had no catalog Inputs", file=sys.stderr, flush=True)
        return 1

    out_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"[export_catalog] wrote {out_path}", flush=True)
    for key in ("Door Inner", "TTF", "Seat Variable", "Airbag"):
        if key in catalog:
            print(f"  {key}={catalog[key]!r}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
