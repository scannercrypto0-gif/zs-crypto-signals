"""ORDER-025 PRIVATE GitHub release custody: local upload / offline downloaded verification.

This program never downloads market data, modifies old ZIP bytes, commits raw
files, tunes any strategy, or publishes a signal. Only explicit 'upload' invokes
GitHub CLI, after a separate owner's rights-and-hosting acknowledgement.
GitHub release assets are accessible to authorized repository collaborators:
private does not mean an immutable archive or legal redistribution permission.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from zs_smart_gate.setup021 import CONFIG_SHA256
from zs_smart_gate.stage03_order022 import (
    MONTHS, SYMBOLS, ResearchBlocked, canonical, file_sha, filename, read_protocol,
)

REPO = "scannercrypto0-gif/zs-crypto-signals"
TAG = "order022-private-010b-2025-v1"
ORIGINAL_MANIFEST_SHA = "45116717abe2ddda7d906ab5bf97a5507a39720c64fbbd175e7daf2c4e67c738"
ORIGINAL_INDEX_SHA = "ce0a3716f24612ea04427b12454e420f9f7e10a0a9bedd622c0ac866a372da79"
REPORT_SHA = "985abecf489ea23d1e46f9aace7152df8cf997cd94cce33dde440bdb34cea5ee"
PER_ZIP_CAP = 12 * 1024 * 1024
EVIDENCE_CAP = 128 * 1024 * 1024
METADATA_NAMES = (
    "frozen-experiment.json",
    "private-run-receipt.json",
    "historical-price-only-report.json",
    "research-results.sqlite",
    "verified-restore.sqlite",
)
OPTIONAL_NAMES = ("freeze-receipt.json", "inventory.json", "local-010b-catalog.json")
FORBIDDEN = {".git", ".venv", "__pycache__"}
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def _sha(path):
    if not path.is_file() or path.is_symlink():
        raise ResearchBlocked("SOURCE_REQUIRED_REGULAR_FILE")
    return file_sha(path)


def find_previous(root, name, required_sha, limit=5):
    root = Path(root).resolve(strict=True)
    matches = []
    for parent, dirs, names in os.walk(root, followlinks=False):
        depth = len(Path(parent).relative_to(root).parts)
        dirs[:] = [d for d in dirs if d not in FORBIDDEN
                   and not (Path(parent) / d).is_symlink()] if depth < limit else []
        if name in names:
            p = Path(parent) / name
            if p.is_file() and not p.is_symlink() and p.stat().st_size <= EVIDENCE_CAP:
                if _sha(p) == required_sha:
                    matches.append(p)
    if not matches:
        raise ResearchBlocked("PREVIOUS_PIN_NOT_FOUND:" + name)
    return sorted(matches, key=lambda p: str(p))[0]


def read_json(path):
    if path.stat().st_size > EVIDENCE_CAP:
        raise ResearchBlocked("OVERSIZED_EVIDENCE_FILE")
    return json.loads(path.read_bytes())


def locally_pinned_inputs(original_root, private_run):
    """Read-only; fail BEFORE a release is created or any GitHub upload begins."""
    old_dir = Path(original_root).resolve(strict=True)
    run = Path(private_run).resolve(strict=True)
    if old_dir == run or old_dir in run.parents or run in old_dir.parents:
        raise ResearchBlocked("SOURCE_AND_REPORT_ROOTS_MUST_BE_SEPARATE")
    old_path = find_previous(old_dir, "manifest.json", ORIGINAL_MANIFEST_SHA)
    index = find_previous(old_dir, "dataset-index.json", ORIGINAL_INDEX_SHA)
    old = read_json(old_path)
    raw_entries = old.get("files")
    if not isinstance(raw_entries, list):
        raise ResearchBlocked("ORIGINAL_MANIFEST_SCHEMA_MISSING")
    old_pins = {}
    for e in raw_entries:
        if not isinstance(e, dict):
            raise ResearchBlocked("ORIGINAL_MANIFEST_ENTRY_INVALID")
        for sym in SYMBOLS:
            for month in MONTHS:
                if (e.get("name") == filename(sym, month)
                        and e.get("symbol") == sym and e.get("interval") == "5m"):
                    key = (sym, month)
                    if key in old_pins:
                        raise ResearchBlocked("ORIGINAL_SOURCE_PIN_DUPLICATED")
                    h = e.get("sha256")
                    if not isinstance(h, str) or not SHA_PATTERN.fullmatch(h):
                        raise ResearchBlocked("ORIGINAL_SOURCE_PIN_MALFORMED")
                    old_pins[key] = h
    expected = {(s, m) for s in SYMBOLS for m in MONTHS}
    if set(old_pins) != expected:
        raise ResearchBlocked("ORIGINAL_SOURCE_PINS_NOT_TWELVE")

    for name in METADATA_NAMES:
        p = run / name
        if not p.is_file() or p.is_symlink() or p.stat().st_size > EVIDENCE_CAP:
            raise ResearchBlocked("PRIVATE_RUN_EVIDENCE_MISSING:" + name)
    frozen_path = run / "frozen-experiment.json"
    manifest = read_json(frozen_path)
    report_path = run / "historical-price-only-report.json"
    if _sha(report_path) != REPORT_SHA:
        raise ResearchBlocked("REPORTED_HISTORICAL_REPORT_SHA_MISMATCH")
    receipt = read_json(run / "private-run-receipt.json")
    report = read_json(report_path)
    proto, proto_sha = read_protocol()
    if (manifest.get("schema") != "ORDER022_FROZEN_EXPERIMENT_V1"
            or manifest.get("source_kind") != "REAL_ARCHIVE_PRIVATE"
            or manifest.get("protocol_sha256") != proto_sha
            or report.get("protocol_sha256") != proto_sha
            or manifest.get("setup_contract_sha256") != CONFIG_SHA256
            or report.get("setup_contract_sha256") != CONFIG_SHA256):
        raise ResearchBlocked("FROZEN_SOURCE_CONTRACT_MISMATCH")
    if (_sha(frozen_path) != receipt.get("frozen_manifest_sha256")
            or _sha(frozen_path) != report.get("manifest_sha256")
            or receipt.get("result_report_sha256") != REPORT_SHA):
        raise ResearchBlocked("FROZEN_RECEIPT_REPORT_CHAIN_MISMATCH")
    if report.get("publishable") is not False or report.get("market_requests") != 0:
        raise ResearchBlocked("UNEXPECTED_LIVE_OR_PUBLICATION_CLAIM")
    if (manifest.get("module_sha256") != _sha(
            Path(__file__).resolve().parents[1] / "src/zs_smart_gate/stage03_order022.py")
            or manifest.get("setup_module_sha256") != _sha(
            Path(__file__).resolve().parents[1] / "src/zs_smart_gate/setup021.py")):
        raise ResearchBlocked("ORIGINAL_REPLAY_ENGINE_CODE_CHANGED")

    frozen_entries = manifest.get("archives")
    if not isinstance(frozen_entries, list) or len(frozen_entries) != 12:
        raise ResearchBlocked("FROZEN_ARCHIVES_NOT_TWELVE")
    frozen_pins = {}
    for e in frozen_entries:
        key = (e.get("symbol"), e.get("month"))
        if key in frozen_pins or key not in expected or e.get("name") != filename(*key):
            raise ResearchBlocked("FROZEN_SOURCE_NAMES_INVALID")
        frozen_pins[key] = e.get("sha256")
    if frozen_pins != old_pins:
        raise ResearchBlocked("ORIGINAL_AND_REPLAY_SOURCE_HASHES_DISAGREE")

    assets = {"manifest.json":old_path, "dataset-index.json":index}
    for sym, month in sorted(expected):
        name = filename(sym, month)
        # Require original owner-retained file and reported staging to match
        # same old frozen hash. Upload the ORIGINAL path, never the staged copy.
        original = find_previous(old_dir, name, old_pins[(sym, month)])
        duplicate = run / "verified_5m_archives" / name
        if (original.stat().st_size > PER_ZIP_CAP or
                _sha(duplicate) != old_pins[(sym, month)]):
            raise ResearchBlocked("ORIGINAL_ZIP_OR_PRIVATE_STAGING_CHANGED:" + name)
        assets[name] = original
    for name in METADATA_NAMES:
        assets[name] = run / name
    for name in OPTIONAL_NAMES:
        p = run / name
        if p.is_file() and not p.is_symlink() and p.stat().st_size <= EVIDENCE_CAP:
            assets[name] = p
    # These are SHA/size metadata only, never raw source values or local paths.
    index_doc = {
        "schema": "ORDER025_GITHUB_PRIVATE_RELEASE_ASSET_INDEX_V1",
        "repo": REPO, "tag": TAG, "repository_visibility": "PRIVATE_REQUIRED",
        "data_origin": "OWNER_010B_EXISTING_ARCHIVE_BYTES_NO_REDOWNLOAD",
        "old_manifest_sha256": ORIGINAL_MANIFEST_SHA,
        "old_dataset_index_sha256": ORIGINAL_INDEX_SHA,
        "report_sha256": REPORT_SHA,
        "frozen_manifest_sha256": _sha(frozen_path),
        "setup_contract_sha256": CONFIG_SHA256,
        "protocol_sha256": proto_sha,
        "legal_scope": "OWNER_PERSONAL_NONCOMMERCIAL_RESEARCH_SUBJECT_TO_DATA_LICENSE",
        "publication_time_or_pit": "NOT_ATTESTED",
        "scientific_status": "NOT_YET_INDEPENDENTLY_REPRODUCED",
        "asset_hashes": {
            name: {"sha256": _sha(p), "bytes": p.stat().st_size}
            for name, p in sorted(assets.items())
        },
    }
    return assets, index_doc


def verify_download(directory, *, require_transfer_receipt=False):
    directory = Path(directory).resolve(strict=True)
    idx_path = directory / "asset-index.json"
    if not idx_path.is_file() or idx_path.is_symlink():
        raise ResearchBlocked("GITHUB_ASSET_INDEX_MISSING")
    idx = read_json(idx_path)
    if (idx.get("schema") != "ORDER025_GITHUB_PRIVATE_RELEASE_ASSET_INDEX_V1"
            or idx.get("repo") != REPO or idx.get("tag") != TAG
            or idx.get("report_sha256") != REPORT_SHA
            or idx.get("old_manifest_sha256") != ORIGINAL_MANIFEST_SHA
            or idx.get("old_dataset_index_sha256") != ORIGINAL_INDEX_SHA
            or idx.get("repository_visibility") != "PRIVATE_REQUIRED"):
        raise ResearchBlocked("GITHUB_ASSET_INDEX_UNEXPECTED")
    hashes = idx.get("asset_hashes")
    if not isinstance(hashes, dict):
        raise ResearchBlocked("GITHUB_ASSET_LIST_INVALID")
    expected_names = {filename(s, m) for s in SYMBOLS for m in MONTHS}
    expected_names |= set(METADATA_NAMES) | {"manifest.json", "dataset-index.json"}
    if not expected_names.issubset(hashes):
        raise ResearchBlocked("GITHUB_ASSET_LIST_INCOMPLETE")
    actual_files = {p.name for p in directory.iterdir() if p.is_file()}
    expected_files = set(hashes) | {"asset-index.json"}
    # An owner upload writes this *after* verifying the original release.
    # The ACTIONS download therefore sees one additional digest-only receipt.
    receipt_path = directory / "transfer-verification.json"
    if require_transfer_receipt and (not receipt_path.is_file() or receipt_path.is_symlink()):
        raise ResearchBlocked("GITHUB_TRANSFER_RECEIPT_REQUIRED")
    if receipt_path.is_file():
        transfer_receipt = read_json(receipt_path)
        if (transfer_receipt.get("status") != "GITHUB_TRANSFER_HASHES_VERIFIED"
                or transfer_receipt.get("asset_index_sha256") != _sha(idx_path)
                or transfer_receipt.get("zip_count") != 12):
            raise ResearchBlocked("GITHUB_TRANSFER_RECEIPT_MISMATCH")
        expected_files.add("transfer-verification.json")
    if actual_files != expected_files:
        raise ResearchBlocked("GITHUB_ASSET_SET_UNEXPECTED")
    for name, stat in sorted(hashes.items()):
        if not isinstance(name, str) or Path(name).name != name or name.startswith("."):
            raise ResearchBlocked("GITHUB_ASSET_NAME_INVALID")
        if (not isinstance(stat, dict) or
                not isinstance(stat.get("sha256"), str) or
                not SHA_PATTERN.fullmatch(stat["sha256"])):
            raise ResearchBlocked("GITHUB_ASSET_HASH_MALFORMED")
        p = directory / name
        if p.is_symlink() or not p.is_file() or p.stat().st_size != stat.get("bytes"):
            raise ResearchBlocked("GITHUB_ASSET_SIZE_MISMATCH")
        if _sha(p) != stat["sha256"]:
            raise ResearchBlocked("GITHUB_ASSET_SHA_MISMATCH")
    if sum(name.endswith(".zip") for name in hashes) != 12:
        raise ResearchBlocked("GITHUB_ZIP_COUNT_NOT_TWELVE")
    if (_sha(directory/"manifest.json") != ORIGINAL_MANIFEST_SHA or
            _sha(directory/"dataset-index.json") != ORIGINAL_INDEX_SHA or
            _sha(directory/"historical-price-only-report.json") != REPORT_SHA or
            _sha(directory/"frozen-experiment.json") != idx.get("frozen_manifest_sha256")):
        raise ResearchBlocked("GITHUB_ORIGINAL_EVIDENCE_SHA_MISMATCH")
    return {"status":"GITHUB_TRANSFER_HASHES_VERIFIED",
            "repo":REPO,"tag":TAG,"assets":len(hashes),"zip_count":12,
            "report_sha256":REPORT_SHA,
            "asset_index_sha256":_sha(idx_path),
            "historical_pit":"UNVERIFIED","scientific_pass":False}


def gh(args, *, allow_failure=False):
    cmd = ["gh", *args, "--repo", REPO] if args[:2] and args[0] == "release" else ["gh", *args]
    try:
        result = subprocess.run(cmd, text=True, capture_output=True, timeout=600)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ResearchBlocked("GITHUB_CLI_NOT_AVAILABLE_OR_TIMEOUT") from exc
    if result.returncode and not allow_failure:
        raise ResearchBlocked("GITHUB_OPERATION_FAILED:" + args[0] + "_" + args[1])
    return result


def assert_remote_private():
    r = gh(["repo", "view", REPO, "--json", "visibility", "--jq", ".visibility"])
    if r.stdout.strip().upper() != "PRIVATE":
        raise ResearchBlocked("REMOTE_REPOSITORY_NOT_PRIVATE")


def upload(original, private_run, *, rights_reviewed):
    if rights_reviewed is not True:
        raise ResearchBlocked("DATA_LICENSE_AND_PRIVATE_HOSTING_REVIEW_REQUIRED")
    assets, index_doc = locally_pinned_inputs(original, private_run)
    assert_remote_private()
    if gh(["release", "view", TAG], allow_failure=True).returncode == 0:
        raise ResearchBlocked("SOURCE_RELEASE_TAG_ALREADY_EXISTS_NO_OVERWRITE")
    with tempfile.TemporaryDirectory(prefix="order025-gh-release-") as temp:
        temp = Path(temp)
        index_path = temp / "asset-index.json"
        index_path.write_bytes(canonical(index_doc)+b"\n")
        notes = temp / "release-notes.md"
        notes.write_text(
            "ORDER-022 original market archives. OWNER-RESTRICTED PRIVATE personal "
            "noncommercial research only; Binance Vision attribution; subject to "
            "applicable dataset rights. Not production, not source PIT proof. "
            "Do not change repository visibility or mirror assets. "
            "This release is not proof of independent scientific verification.\n",
            encoding="utf-8")
        gh(["release", "create", TAG, "--title", "ORDER022 PRIVATE preserved 010-B original bytes",
            "--notes-file", str(notes), "--prerelease", "--latest=false",
            "--target", "05ced43dcfbc476a60030283004503945be82120",
            *[str(p) for p in assets.values()], str(index_path)])
        assert_remote_private()
        check_dir = temp / "download-verify"
        check_dir.mkdir()
        gh(["release", "download", TAG, "--dir", str(check_dir)])
        receipt = verify_download(check_dir)
        receipt_path = temp / "transfer-verification.json"
        receipt_path.write_bytes(canonical(receipt)+b"\n")
        gh(["release", "upload", TAG, str(receipt_path)])
        # Extra transferred receipt is not part of the original input manifest;
        # it is an independent completion record with separately verified bytes.
        print(json.dumps({
            "status":"OWNER_PRIVATE_GITHUB_TRANSFER_BYTES_VERIFIED",
            "release_tag":TAG,"zip_count":12,
            "asset_index_sha256":receipt["asset_index_sha256"],
            "historical_pit":"UNVERIFIED","real_replay_audit":"NOT_RUN_IN_GITHUB_ACTIONS",
            "market_requests":0
        },sort_keys=True))


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline source custody → PRIVATE GitHub release")
    sub = p.add_subparsers(dest="action", required=True)
    prepare = sub.add_parser("preflight")
    upload_p = sub.add_parser("upload")
    for sp in (prepare,upload_p):
        sp.add_argument("--original-root", required=True)
        sp.add_argument("--private-run-dir", required=True)
    upload_p.add_argument("--rights-reviewed", action="store_true")
    verify_p = sub.add_parser("verify")
    verify_p.add_argument("--download-dir", required=True)
    verify_p.add_argument("--require-transfer-receipt", action="store_true")
    args = p.parse_args(argv)
    try:
        if args.action == "verify":
            print(json.dumps(verify_download(args.download_dir,
                       require_transfer_receipt=args.require_transfer_receipt),sort_keys=True))
        elif args.action == "preflight":
            _, doc = locally_pinned_inputs(args.original_root,args.private_run_dir)
            print(json.dumps({"status":"LOCAL_SOURCE_SHA_PREFLIGHT_PASS_NO_UPLOAD",
                              "original_zip_count":12,
                              "asset_count":len(doc["asset_hashes"]),
                              "report_sha256":REPORT_SHA,"market_requests":0}))
        else:
            upload(args.original_root,args.private_run_dir,
                   rights_reviewed=args.rights_reviewed)
    except (ResearchBlocked, OSError, ValueError, KeyError, TypeError) as exc:
        # Never reveal original Windows file paths or archive contents in logs.
        reason = str(exc).split(":",1)[0]
        print(json.dumps({"status":"TRANSFER_BLOCKED","reason":reason,
                          "market_requests":0},sort_keys=True),file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
