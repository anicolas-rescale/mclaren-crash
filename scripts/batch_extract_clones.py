#!/usr/bin/env python3
"""Batch-create McLaren Utilities extract clones (HLfJXb recipe) via EU Rescale API.

Modes:
  --dry-run   list queue / skips; no create
  --pilot     create+submit ONE child, poll for artifacts, exit (human gate)
  --serial    create+submit remaining queue one-at-a-time (ONLY after go-ahead)

Auth: RESCALE_API_KEY env, or mclaren-crash-pole/.venv (KEY=value file).
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

REPO = Path(__file__).resolve().parents[1]
DOE_PATH = REPO / "examples" / "lsdyna-doe.json"
DEFAULT_MANIFEST = REPO / "scripts" / "batch_extract_manifest.csv"
BASE_DEFAULT = "https://eu.rescale.com"

# Starter-23 sync jobs from docs/ls-dyna-extraction-plan.md
STARTER_IDS: List[str] = [
    "HFuKPb",
    "ctowac",
    "OQuKPb",
    "Qhowac",
    "BFuKPb",
    "MQuKPb",
    "zFuKPb",
    "xHdsac",
    "ifkFPb",
    "gfkFPb",
    "ixdsac",
    "UUjFPb",
    "pHdsac",
    "afkFPb",
    "cxdsac",
    "OUjFPb",
    "YekFPb",
    "axdsac",
    "MUjFPb",
    "vVwVXb",
    "EbjaNb",
    "exteNb",
    "TAfpEc",
]

LOADCASE_TAG = "psaf:loadcase:os_es2re_pole32"
EXCLUDE_PREFIX = "surrogate:exclude"
# Old 0.1.13 / 0.2.17 extracts in HxPaa. New DOE-probe clones (0.1.14 / 0.2.18)
# must NOT get this tag — leave it on the prior corpus only.
POSTPROCESS_TAG = "crashPostProcess"
# Side_Pole_Data_Occupant — https://eu.rescale.com/folders/HxPaa/
TARGET_FOLDER_ID = "HxPaa"

# Gold extract template (HLfJXb)
TEMPLATE_ANALYSIS = {"code": "rescale_utils_lnx", "version": "v2025.12.16-sxp"}
TEMPLATE_HARDWARE = {
    "coreType": "emerald",
    "coresPerSlot": 18,
    "slots": 1,
    "walltime": 2,
}
TEMPLATE_COMMAND = (
    'echo "mclaren postproc — extractors on tiles"\n'
    "ls -la\n"
    "find . -maxdepth 3 \\( -name 'd3plot' -o -name 'd3plot*' "
    "-o -name 'lsdyna-doe.json' \\) 2>/dev/null | head -40"
)
META_AUTOMATION_ID = "Bwuia"
AI_AUTOMATION_ID = "QYnVk"
AI_ENV = {
    "AUTOMATION_ANALYSIS": "ls_dyna",
    "NODAL_SCALARS": "none",
}

ARTIFACT_NAMES = ("case_data.vtp", "case_data.stl", "case_data.yml")


def load_api_key() -> str:
    env = os.getenv("RESCALE_API_KEY", "").strip()
    if env:
        return env
    venv = REPO / ".venv"
    if venv.is_file():
        text = venv.read_text().strip()
        if "=" in text:
            return text.split("=", 1)[1].strip()
        return text
    raise SystemExit("Missing RESCALE_API_KEY / .venv")


class RescaleClient:
    def __init__(self, base: str, token: str) -> None:
        self.base = base.rstrip("/")
        self.token = token

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        data: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 300,
    ) -> Any:
        url = path if path.startswith("http") else f"{self.base}{path}"
        hdrs = {"Authorization": f"Token {self.token}"}
        if headers:
            hdrs.update(headers)
        body = data
        if json_body is not None:
            body = json.dumps(json_body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        last_err: Optional[Exception] = None
        for attempt in range(1, 13):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                    if not raw:
                        return None
                    ctype = resp.headers.get("Content-Type", "")
                    if "json" in ctype or raw[:1] in (b"{", b"["):
                        return json.loads(raw.decode())
                    return raw
            except urllib.error.HTTPError as e:
                err = e.read().decode(errors="replace")
                raise RuntimeError(f"{method} {path} -> HTTP {e.code}: {err[:800]}") from e
            except (TimeoutError, urllib.error.URLError, ConnectionResetError, OSError) as e:
                last_err = e
                sleep_s = min(60, 5 * attempt)
                print(
                    f"[retry] {method} {path} attempt {attempt}/12 "
                    f"err={type(e).__name__}: {e}; sleep {sleep_s}s",
                    flush=True,
                )
                time.sleep(sleep_s)
                # Request objects can only be reused carefully; rebuild
                req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        raise RuntimeError(f"{method} {path} failed after retries: {last_err}") from last_err

    def get(self, path: str, **kw: Any) -> Any:
        return self._request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> Any:
        return self._request("POST", path, **kw)

    def patch(self, path: str, **kw: Any) -> Any:
        return self._request("PATCH", path, **kw)

    def delete(self, path: str, **kw: Any) -> Any:
        return self._request("DELETE", path, **kw)

    def paginate(self, path: str) -> Iterable[Dict[str, Any]]:
        url = path
        while url:
            page = self.get(url)
            results = page.get("results") if isinstance(page, dict) else page
            if not isinstance(results, list):
                return
            for item in results:
                yield item
            nxt = page.get("next") if isinstance(page, dict) else None
            if not nxt:
                break
            url = nxt if nxt.startswith("http") else nxt


def tag_names(job: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for t in job.get("userTags") or []:
        if isinstance(t, dict):
            out.append(str(t.get("name") or ""))
        else:
            out.append(str(t))
    return [t for t in out if t]


def has_exclude(tags: Sequence[str]) -> bool:
    return any(t.startswith(EXCLUDE_PREFIX) for t in tags)


def job_latest_status(client: RescaleClient, job_id: str) -> str:
    page = client.get(f"/api/v2/jobs/{job_id}/statuses/")
    results = (page or {}).get("results") or []
    if not results:
        return "UNKNOWN"
    # API returns newest first for HLfJXb
    return str(results[0].get("status") or "UNKNOWN")


def list_job_files(client: RescaleClient, job_id: str) -> List[Dict[str, Any]]:
    return list(client.paginate(f"/api/v2/jobs/{job_id}/files/?page_size=100"))


def file_names(files: Sequence[Dict[str, Any]]) -> Set[str]:
    return {str(f.get("name") or "") for f in files}


def has_extract_artifacts(client: RescaleClient, job_id: str) -> bool:
    names = file_names(list_job_files(client, job_id))
    return all(n in names for n in ARTIFACT_NAMES)


def index_extract_children(client: RescaleClient) -> Dict[str, str]:
    """Map parent_id -> child_id for owned extract clones."""
    out: Dict[str, str] = {}
    # Known successes (list payloads often omit clonedFrom)
    out["HFuKPb"] = "HLfJXb"
    out["ctowac"] = "gNHKPb"
    out["OQuKPb"] = "raMAac"
    out["Qhowac"] = "SicTPb"
    out["BFuKPb"] = "PUfJXb"
    out["MQuKPb"] = "odxaNb"
    out["zFuKPb"] = "EDGeNb"
    out["xHdsac"] = "GRKVXb"
    out["gfkFPb"] = "bcLVXb"
    out["ixdsac"] = "JDrsac"

    candidates: List[str] = []
    for job in client.paginate("/api/v2/jobs/?f=1&page_size=100"):
        jid = str(job.get("id") or "")
        name = job.get("name") or ""
        parent = job.get("clonedFrom")
        if parent:
            out.setdefault(str(parent), jid)
            continue
        if jid and (
            POSTPROCESS_TAG.lower() in str(job.get("userTags") or "").lower()
            or "Extraction" in name
            or "PostProc" in name
        ):
            candidates.append(jid)

    for jid in candidates:
        try:
            detail = client.get(f"/api/v2/jobs/{jid}/")
        except Exception:
            continue
        parent = detail.get("clonedFrom")
        if parent:
            out.setdefault(str(parent), jid)
    return out


def find_existing_extract_child(
    client: RescaleClient,
    parent_id: str,
    *,
    child_index: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Return an extract child job id if one already exists for parent."""
    idx = child_index if child_index is not None else index_extract_children(client)
    return idx.get(parent_id)


def upload_doe(client: RescaleClient, path: Path) -> str:
    boundary = "----RescaleBoundary7MA4YWxkTrZu0gW"
    data = path.read_bytes()
    filename = path.name
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/json\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    resp = client._request(
        "POST",
        "/api/v2/files/contents/",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=300,
    )
    if not isinstance(resp, dict) or not resp.get("id"):
        raise RuntimeError(f"DOE upload failed: {resp!r}")
    return str(resp["id"])


def build_job_payload(
    *,
    parent: Dict[str, Any],
    input_file_ids: Sequence[str],
    doe_file_id: str,
    folder_id: str = TARGET_FOLDER_ID,
) -> Dict[str, Any]:
    parent_id = parent["id"]
    parent_name = parent.get("name") or parent_id
    files = [{"id": fid} for fid in input_file_ids]
    files.append({"id": doe_file_id})
    return {
        "name": f"{parent_name} (Extraction Tiles EU)",
        "clonedFrom": parent_id,
        "folderId": folder_id,
        "jobanalyses": [
            {
                "analysis": dict(TEMPLATE_ANALYSIS),
                "command": TEMPLATE_COMMAND,
                "hardware": dict(TEMPLATE_HARDWARE),
                "inputFiles": files,
            }
        ],
        "jobAutomations": [
            {
                "automation": {"id": META_AUTOMATION_ID},
                "environmentVariables": {},
            },
            {
                "automation": {"id": AI_AUTOMATION_ID},
                "environmentVariables": dict(AI_ENV),
            },
        ],
    }


def add_tag(client: RescaleClient, job_id: str, name: str) -> None:
    client.post(f"/api/v2/jobs/{job_id}/tags/", json_body={"name": name})


def remove_tag(client: RescaleClient, job_id: str, name: str) -> None:
    """Drop a job tag if present. Rescale tag DELETE is by name query."""
    encoded = urllib.parse.quote(name, safe="")
    try:
        client.delete(f"/api/v2/jobs/{job_id}/tags/{encoded}/")
        return
    except Exception:
        pass
    client.delete(f"/api/v2/jobs/{job_id}/tags/?name={encoded}")


def move_job_to_folder(
    client: RescaleClient,
    job_id: str,
    folder_id: str,
) -> None:
    """Ensure job lives in Side_Pole_Data_Occupant (HxPaa)."""
    job = client.get(f"/api/v2/jobs/{job_id}/")
    current = job.get("folderId")
    if current == folder_id:
        print(f"[folder] {job_id} already in {folder_id}")
        return
    client.patch(f"/api/v2/jobs/{job_id}/", json_body={"folderId": folder_id})
    verify = client.get(f"/api/v2/jobs/{job_id}/").get("folderId")
    print(f"[folder] {job_id} {current!r} -> {verify!r}")
    if verify != folder_id:
        raise RuntimeError(f"{job_id}: folder move failed (got {verify!r})")


def create_and_submit(
    client: RescaleClient,
    *,
    parent: Dict[str, Any],
    doe_file_id: str,
    folder_id: str = TARGET_FOLDER_ID,
    dry_create_only: bool = False,
) -> str:
    parent_id = parent["id"]
    parent_files = list_job_files(client, parent_id)
    if not parent_files:
        raise RuntimeError(f"{parent_id}: no files to clone as inputs")
    file_ids = [str(f["id"]) for f in parent_files if f.get("id")]
    # Avoid duplicating an already-present lsdyna-doe.json from parent
    parent_names = {str(f.get("name") or "") for f in parent_files}
    payload = build_job_payload(
        parent=parent,
        input_file_ids=file_ids,
        doe_file_id=doe_file_id,
        folder_id=folder_id,
    )
    if "lsdyna-doe.json" in parent_names:
        # still force our DOE id last; platform may keep both — OK
        pass

    print(
        f"[create] parent={parent_id} files={len(file_ids)} "
        f"name={payload['name']!r}"
    )
    created = client.post("/api/v2/jobs/", json_body=payload, timeout=300)
    child_id = created["id"]
    print(f"[create] child={child_id}")

    # Keep loadcase; do not tag new extracts crashPostProcess (old corpus only).
    if LOADCASE_TAG in tag_names(parent):
        try:
            add_tag(client, child_id, LOADCASE_TAG)
        except Exception as e:
            print(f"[warn] could not copy loadcase tag: {e}")
    try:
        if POSTPROCESS_TAG in tag_names(client.get(f"/api/v2/jobs/{child_id}/")):
            remove_tag(client, child_id, POSTPROCESS_TAG)
            print(f"[tags] stripped inherited {POSTPROCESS_TAG} from {child_id}")
    except Exception as e:
        print(f"[warn] could not strip {POSTPROCESS_TAG}: {e}")

    tags = client.get(f"/api/v2/jobs/{child_id}/tags/")
    print(f"[tags] {child_id} -> {tags}")

    try:
        move_job_to_folder(client, child_id, folder_id)
    except Exception as e:
        print(f"[warn] folder move after create failed: {e}")

    if dry_create_only:
        print(f"[create] draft-only; not submitting {child_id}")
        return child_id

    try:
        client.post(f"/api/v2/jobs/{child_id}/submit/")
        print(f"[submit] {child_id}")
    except RuntimeError as e:
        msg = str(e)
        if "400" in msg and "started" in msg.lower():
            print(f"[submit] {child_id} already started; continuing")
        else:
            raise
    return child_id


def wait_for_extract(
    client: RescaleClient,
    job_id: str,
    *,
    poll_s: int = 60,
    timeout_s: int = 6 * 3600,
) -> Tuple[str, bool]:
    t0 = time.time()
    terminal = {
        "Completed",
        "COMPLETED",
        "Failed",
        "FAILED",
        "Stopped",
        "STOPPED",
        "Force Stop",
        "FORCE_STOP",
    }
    last = ""
    while True:
        try:
            status = job_latest_status(client, job_id)
        except RuntimeError as e:
            print(f"[poll] {job_id} transient API error: {e}; retry in {poll_s}s", flush=True)
            time.sleep(poll_s)
            continue
        if status != last:
            print(f"[poll] {job_id} status={status}")
            last = status
        if status in terminal:
            ok = has_extract_artifacts(client, job_id)
            print(f"[poll] {job_id} terminal={status} artifacts_ok={ok}")
            return status, ok
        if time.time() - t0 > timeout_s:
            raise TimeoutError(f"{job_id} timed out after {timeout_s}s (last={status})")
        time.sleep(poll_s)


def classify_starter(
    client: RescaleClient,
    *,
    force_new: bool = False,
    skip_parents: Optional[Sequence[str]] = None,
) -> Tuple[List[Dict[str, Any]], List[Tuple[str, str]]]:
    eligible: List[Dict[str, Any]] = []
    skipped: List[Tuple[str, str]] = []
    skip_set = {s.strip() for s in (skip_parents or []) if s.strip()}
    child_index: Dict[str, str] = {}
    if force_new:
        print("[index] force-new: skip owned-child scan", flush=True)
    else:
        print("[index] scanning owned extract children…", flush=True)
        child_index = index_extract_children(client)
        print(f"[index] {len(child_index)} parent→child maps", flush=True)
    for jid in STARTER_IDS:
        if jid in skip_set:
            skipped.append((jid, "skip_parent"))
            continue
        try:
            job = client.get(f"/api/v2/jobs/{jid}/")
        except Exception as e:
            skipped.append((jid, f"fetch_error:{e}"))
            continue
        tags = tag_names(job)
        if has_exclude(tags):
            skipped.append((jid, f"exclude:{','.join(tags)}"))
            continue
        if LOADCASE_TAG not in tags:
            skipped.append((jid, f"no_loadcase_tag:{','.join(tags)}"))
            continue
        existing = find_existing_extract_child(
            client, jid, child_index=child_index
        )
        if existing and not force_new:
            skipped.append((jid, f"already_extracted:{existing}"))
            continue
        if existing and force_new:
            print(f"[index] {jid} has old extract {existing}; forcing new clone")
        eligible.append(job)
    return eligible, skipped


def append_manifest(
    path: Path,
    row: Dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "parent_id",
                "parent_name",
                "child_id",
                "status",
                "vtp_ok",
                "notes",
            ],
        )
        if write_header:
            w.writeheader()
        w.writerow(row)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--pilot", nargs="?", const="__AUTO__", metavar="PARENT_ID")
    mode.add_argument("--serial", action="store_true")
    ap.add_argument("--base-url", default=os.getenv("RESCALE_API_BASE_URL", BASE_DEFAULT))
    ap.add_argument("--doe", type=Path, default=DOE_PATH)
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    ap.add_argument("--poll-seconds", type=int, default=60)
    ap.add_argument("--draft-only", action="store_true", help="create draft, do not submit")
    ap.add_argument(
        "--doe-file-id",
        default="",
        help="reuse an already-uploaded lsdyna-doe.json file id",
    )
    ap.add_argument(
        "--folder-id",
        default=TARGET_FOLDER_ID,
        help="Rescale folder id for Side_Pole_Data_Occupant (default HxPaa)",
    )
    ap.add_argument(
        "--force-new",
        action="store_true",
        help="clone even when an older extract child already exists",
    )
    ap.add_argument(
        "--skip-parent",
        action="append",
        default=[],
        help="sync parent id to skip (repeatable), e.g. HFuKPb already smoked as wJNQX",
    )
    args = ap.parse_args(argv)
    folder_id = args.folder_id

    token = load_api_key()
    client = RescaleClient(args.base_url, token)

    print(f"[auth] base={args.base_url} folder={folder_id}")
    eligible, skipped = classify_starter(
        client,
        force_new=args.force_new,
        skip_parents=args.skip_parent,
    )
    print(f"[queue] eligible={len(eligible)} skipped={len(skipped)}")
    for jid, reason in skipped:
        print(f"  skip {jid}: {reason}")
    for job in eligible:
        print(f"  run  {job['id']}: {(job.get('name') or '')[:70]}")

    if args.dry_run:
        print("[dry-run] done — no jobs created")
        return 0

    if not args.doe.is_file() and not args.doe_file_id:
        raise SystemExit(f"DOE map missing: {args.doe}")

    doe_id = args.doe_file_id.strip()
    if not doe_id:
        print(f"[doe] uploading {args.doe}")
        doe_id = upload_doe(client, args.doe)
        print(f"[doe] file_id={doe_id}")

    if args.pilot is not None:
        want = None if args.pilot == "__AUTO__" else args.pilot
        if want:
            parent = next((j for j in eligible if j["id"] == want), None)
            if parent is None:
                # allow pilot of an eligible id even if already listed skipped? no
                parent = client.get(f"/api/v2/jobs/{want}/")
                tags = tag_names(parent)
                if has_exclude(tags) or LOADCASE_TAG not in tags:
                    raise SystemExit(f"pilot parent {want} not eligible: {tags}")
        else:
            if not eligible:
                raise SystemExit("no eligible parents for pilot")
            parent = eligible[0]
        child = create_and_submit(
            client,
            parent=parent,
            doe_file_id=doe_id,
            folder_id=folder_id,
            dry_create_only=args.draft_only,
        )
        if args.draft_only:
            append_manifest(
                args.manifest,
                {
                    "parent_id": parent["id"],
                    "parent_name": parent.get("name"),
                    "child_id": child,
                    "status": "DRAFT",
                    "vtp_ok": False,
                    "notes": "draft-only",
                },
            )
            print(f"[pilot] DRAFT {child} — inspect then submit manually or re-run without --draft-only")
            return 0
        status, ok = wait_for_extract(
            client, child, poll_s=args.poll_seconds
        )
        try:
            move_job_to_folder(client, child, folder_id)
        except Exception as e:
            print(f"[warn] folder move after pilot complete failed: {e}")
        append_manifest(
            args.manifest,
            {
                "parent_id": parent["id"],
                "parent_name": parent.get("name"),
                "child_id": child,
                "status": status,
                "vtp_ok": ok,
                "notes": "pilot",
            },
        )
        print()
        print("=" * 60)
        print("PILOT COMPLETE — STOPPING for human review")
        print(f"  parent : {parent['id']}")
        print(f"  child  : {child}")
        print(f"  status : {status}")
        print(f"  artifacts_ok: {ok}")
        print(f"  folder : {folder_id}")
        print(f"  url    : {args.base_url}/jobs/{child}/")
        print("Do NOT run --serial until Andrea gives go-ahead.")
        print("=" * 60)
        return 0 if ok and status in {"Completed", "COMPLETED"} else 1

    # --serial
    if not eligible:
        print("[serial] nothing to run")
        return 0
    # Ensure already-finished extracts sit in the target folder
    for known in ("HLfJXb", "gNHKPb"):
        try:
            move_job_to_folder(client, known, folder_id)
        except Exception as e:
            print(f"[warn] folder ensure {known}: {e}")

    print(f"[serial] starting {len(eligible)} jobs one-at-a-time")
    print(f"[serial] folder target={folder_id} (Side_Pole_Data_Occupant)")
    failures = 0
    for job in eligible:
        child = create_and_submit(
            client, parent=job, doe_file_id=doe_id, folder_id=folder_id
        )
        status, ok = wait_for_extract(client, child, poll_s=args.poll_seconds)
        try:
            move_job_to_folder(client, child, folder_id)
        except Exception as e:
            print(f"[warn] folder move after complete failed: {e}")
        append_manifest(
            args.manifest,
            {
                "parent_id": job["id"],
                "parent_name": job.get("name"),
                "child_id": child,
                "status": status,
                "vtp_ok": ok,
                "notes": f"serial;folder={folder_id}",
            },
        )
        if not ok or status not in {"Completed", "COMPLETED"}:
            failures += 1
            print(f"[serial] STOP on failure parent={job['id']} child={child}")
            return 1
    print(f"[serial] done failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
