#!/usr/bin/env python3
"""Publish a new version of the FieldBench corpus record on Zenodo via the REST API.

The GitHub->Zenodo webhook auto-archive is broken for this repo (times out on the
many-file zipball), and the browser uploader is flaky. This uploads the archive
directly via the API (a bucket PUT), which is deterministic.

Setup (once): create a Zenodo personal access token with scopes
`deposit:write` and `deposit:actions` at
    https://zenodo.org/account/settings/applications/tokens/new

Run:
    ZENODO_TOKEN=xxxxx python scripts/zenodo_new_version.py \
        --file ~/Desktop/fieldbench-corpus-v0.4.0.zip --version v0.4.0

It creates (or reuses) the new-version draft under the concept record, removes any
carried-over files, uploads the archive, sets the version, and leaves the draft
READY TO PUBLISH. Review it in the UI and click Publish (or pass --publish to
publish automatically). Pass --record to target a different latest-version record id.
"""
from __future__ import annotations
import argparse, os, sys, time
import urllib.request, urllib.error, json, hashlib

BASE = "https://zenodo.org/api"
# Latest PUBLISHED version record id (v0.3.0). newversion works off any published version.
DEFAULT_RECORD = 21577898
RETRIES = 6  # Zenodo throws transient 5xx / "transfer failed" under load; retry with backoff.


def req(method, url, token, data=None, ctype=None, raw=False):
    headers = {"Authorization": f"Bearer {token}"}
    if ctype:
        headers["Content-Type"] = ctype
    last = ""
    for attempt in range(RETRIES):
        r = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(r, timeout=120) as resp:
                body = resp.read()
                return body if raw else json.loads(body or "{}")
        except urllib.error.HTTPError as e:
            msg = e.read().decode()[:500]
            last = f"HTTP {e.code} on {method} {url}\n{msg}"
            # retry Zenodo's transient overload errors; fail fast on real 4xx
            transient = e.code >= 500 or (e.code == 400 and "transfer failed" in msg.lower())
            if not transient:
                sys.exit(last)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"{method} {url} -> {e}"
        if attempt < RETRIES - 1:
            wait = min(2 ** attempt, 30)
            print(f"    transient error (attempt {attempt+1}/{RETRIES}), retrying in {wait}s...")
            time.sleep(wait)
    sys.exit(f"gave up after {RETRIES} attempts:\n{last}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--record", type=int, default=DEFAULT_RECORD)
    ap.add_argument("--publish", action="store_true", help="publish immediately (else leaves a draft)")
    ap.add_argument("--discard", type=int, default=None,
                    help="discard a stuck draft deposition id, then proceed (e.g. --discard 21654057)")
    args = ap.parse_args()
    token = os.environ.get("ZENODO_TOKEN") or sys.exit("set ZENODO_TOKEN")

    if args.discard:
        try:  # best-effort: a 404 (already gone) must not abort the run
            req("DELETE", f"{BASE}/deposit/depositions/{args.discard}", token, raw=True)
            print(f"discarded stuck draft {args.discard}")
        except SystemExit:
            print(f"draft {args.discard} not discardable (already gone?) — continuing")

    path = os.path.expanduser(args.file)
    fname = os.path.basename(path)
    if not os.path.exists(path):
        sys.exit(f"no such file: {path}")

    # 1. create (or reuse) the new-version draft
    nv = req("POST", f"{BASE}/deposit/depositions/{args.record}/actions/newversion", token)
    draft = req("GET", nv["links"]["latest_draft"], token)
    dep_id = draft["id"]
    bucket = draft["links"]["bucket"]
    print(f"draft deposition {dep_id}  ({draft['links']['html']})")

    # 2. remove carried-over / stuck files
    for f in draft.get("files", []):
        req("DELETE", f"{BASE}/deposit/depositions/{dep_id}/files/{f['id']}", token)
        print(f"  removed carried file {f.get('filename')}")

    try:
        # 3. upload the archive via bucket PUT (the reliable path)
        local_md5 = hashlib.md5(open(path, "rb").read()).hexdigest()
        with open(path, "rb") as fp:
            up = req("PUT", f"{bucket}/{fname}", token, data=fp.read(),
                     ctype="application/octet-stream")
        ok = up.get("checksum", "").endswith(local_md5)
        print(f"  uploaded {fname}  size={up.get('size')}  checksum={'OK' if ok else up.get('checksum')}")
        if not ok:
            sys.exit("checksum mismatch — do not publish")

        # 4. set the version field on the draft metadata
        meta = dict(draft["metadata"]); meta["version"] = args.version
        req("PUT", f"{BASE}/deposit/depositions/{dep_id}", token,
            data=json.dumps({"metadata": meta}).encode(), ctype="application/json")
        print(f"  version set to {args.version}")
    except SystemExit:
        # clean up the draft we created so repeated retries don't pile up stuck drafts
        try:
            req("DELETE", f"{BASE}/deposit/depositions/{dep_id}", token, raw=True)
            print(f"  upload failed — discarded draft {dep_id} (no pileup)")
        except SystemExit:
            print(f"  upload failed — could not discard draft {dep_id} (Zenodo down)")
        raise

    if args.publish:
        pub = req("POST", f"{BASE}/deposit/depositions/{dep_id}/actions/publish", token)
        print(f"PUBLISHED: DOI {pub.get('doi')}  {pub['links'].get('record_html')}")
    else:
        print(f"\nDraft ready. Review + Publish here:\n  {draft['links']['html']}")


if __name__ == "__main__":
    main()
