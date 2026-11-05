"""One-shot private offline import of previously acquired ORDER-010-B archives.

No network, trading, Telegram, or qualified signals. Original source stays on
the owner's private disk; only a new private local staging copy is made.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from zs_smart_gate.stage03_order022 import (
    MONTHS, SYMBOLS, ResearchBlocked, canonical, file_sha, filename,
    freeze, inventory, run,
)

# SHA-256 values reported in the accepted historical 010-B evidence ledger.
LEGACY_MANIFEST_SHA256 = "45116717abe2ddda7d906ab5bf97a5507a39720c64fbbd175e7daf2c4e67c738"
LEGACY_INDEX_SHA256 = "ce0a3716f24612ea04427b12454e420f9f7e10a0a9bedd622c0ac866a372da79"
EXPECTED = {(symbol, month) for symbol in SYMBOLS for month in MONTHS}


def private_files(root, leaf, *, max_depth=5):
    """Bounded local walk; no directory junctions or symlink traversal."""
    root = Path(root).resolve(strict=True)
    for parent, dirs, names in os.walk(root, followlinks=False):
        depth = len(Path(parent).relative_to(root).parts)
        dirs[:] = [d for d in dirs if d not in (".git", ".venv", "__pycache__")
                   and not (Path(parent) / d).is_symlink()] if depth < max_depth else []
        if leaf in names:
            path = Path(parent) / leaf
            if path.is_file() and not path.is_symlink():
                yield path


def locate_by_pinned_sha(root, name, sha, *, required=True):
    candidates = list(private_files(root, name))
    matches = [p for p in candidates if p.stat().st_size <= 2_000_000 and file_sha(p) == sha]
    if matches:
        return sorted(matches, key=lambda p: str(p))[0]
    if required:
        raise ResearchBlocked("ORIGINAL_010B_" + name.replace(".", "_").upper() + "_MISSING_OR_SHA_MISMATCH")
    if candidates:
        raise ResearchBlocked("ORIGINAL_010B_INDEX_SHA_MISMATCH")
    return None


def original_010b_files(manifest_path):
    """Read 12 existing prior hashes; never self-attest an unpinned dataset."""
    source = json.loads(Path(manifest_path).read_bytes())
    items = source.get("files")
    if not isinstance(items, list):
        raise ResearchBlocked("OLD_010B_MANIFEST_MISSING_FILES")
    found = {}
    for entry in items:
        if not isinstance(entry, dict):
            raise ResearchBlocked("OLD_010B_MANIFEST_ENTRY_INVALID")
        for symbol, month in EXPECTED:
            if (entry.get("symbol") == symbol and entry.get("interval") == "5m"
                    and entry.get("name") == filename(symbol, month)):
                if (symbol, month) in found:
                    raise ResearchBlocked("OLD_010B_DUPLICATE_SOURCE_PIN")
                sha = entry.get("sha256")
                if (not isinstance(sha, str) or len(sha) != 64
                        or any(ch not in "0123456789abcdef" for ch in sha)):
                    raise ResearchBlocked("OLD_010B_SOURCE_SHA_INVALID")
                found[symbol, month] = sha
    if set(found) != EXPECTED:
        raise ResearchBlocked("OLD_010B_TWELVE_SPOT_5M_PINS_INCOMPLETE")
    return found


def archive_paths(root, pins):
    """Require original archive bytes to match the prior frozen SHA values."""
    result = {}
    for (symbol, month), sha in sorted(pins.items()):
        name = filename(symbol, month)
        candidates = list(private_files(root, name))
        verified = [p for p in candidates if p.stat().st_size <= 12 * 1024 * 1024
                    and file_sha(p) == sha]
        if not verified:
            raise ResearchBlocked("ORIGINAL_010B_ARCHIVE_MISSING_OR_SHA_MISMATCH:" + name)
        result[symbol, month] = sorted(verified, key=lambda p: str(p))[0]
    return result


def save_new(path, value):
    path = Path(path)
    with path.open("xb") as f:
        f.write(canonical(value) + b"\n")
    return file_sha(path)


def perform(root, output):
    source = Path(root).resolve(strict=True)
    destination = Path(output).resolve()
    if source == destination or source in destination.parents:
        raise ResearchBlocked("PRIVATE_OUTPUT_MUST_BE_OUTSIDE_SOURCE_ROOT")
    if destination.exists():
        raise ResearchBlocked("PRIVATE_OUTPUT_MUST_BE_FRESH")
    if any((p / ".git").is_dir() for p in (destination, *destination.parents)):
        raise ResearchBlocked("PRIVATE_OUTPUT_INSIDE_GIT_WORKTREE")

    old_manifest = locate_by_pinned_sha(source, "manifest.json", LEGACY_MANIFEST_SHA256)
    source_index = locate_by_pinned_sha(source, "dataset-index.json", LEGACY_INDEX_SHA256,
                                        required=False)
    pins = original_010b_files(old_manifest)
    originals = archive_paths(source, pins)

    destination.mkdir(parents=True)
    staged = destination / "verified_5m_archives"
    staged.mkdir()
    catalog = {"schema": "ORDER022_SOURCE_CATALOG_V1",
               "source_kind": "REAL_ARCHIVE_PRIVATE",
               "catalog_evidence": "PRIOR_010B_MANIFEST_SHA_PINNED_ARCHIVE_BYTES_VERIFIED",
               "previous_010b_manifest_sha256": LEGACY_MANIFEST_SHA256,
               "previous_010b_dataset_index_sha256": LEGACY_INDEX_SHA256 if source_index else None,
               "historical_pit": "HISTORICAL_REPLAY_PIT_UNVERIFIED",
               "provider_publication_receipt_attested": False,
               "files": []}
    for symbol, month in sorted(pins):
        name = filename(symbol, month)
        old_path = originals[symbol, month]
        target = staged / name
        try:
            os.link(old_path, target)
        except OSError:
            shutil.copyfile(old_path, target)
        if file_sha(target) != pins[symbol, month]:
            raise ResearchBlocked("PRIVATE_STAGED_ARCHIVE_SHA_MISMATCH:" + name)
        catalog["files"].append({
            "name": name, "symbol": symbol, "month": month,
            "sha256": pins[symbol, month],
            "source": "BINANCE_VISION_SPOT_PUBLIC_ARCHIVE",
            # Previously frozen source hash matches actual bytes; the provider
            # checksum sidecar itself has not been reattested in this run.
            "provider_checksum_attested": False,
        })
    catalog_path = destination / "local-010b-catalog.json"
    save_new(catalog_path, catalog)
    coverage = inventory(staged, catalog_path)
    if coverage["status"] != "COMPLETE_PINNED":
        raise ResearchBlocked("PRIOR_MANIFEST_CATALOG_COVERAGE_MISMATCH")
    save_new(destination / "inventory.json", coverage)

    # Freeze source identity, engine & protocol BEFORE any actual DEV/OOS read.
    freeze_receipt = freeze(staged, catalog_path, destination / "frozen-experiment.json")
    save_new(destination / "freeze-receipt.json", freeze_receipt)
    result = run(destination / "frozen-experiment.json", staged,
                 destination / "research-results.sqlite", destination / "verified-restore.sqlite")
    if result["source_kind"] != "REAL_ARCHIVE_PRIVATE":
        raise ResearchBlocked("REAL_RESULT_SOURCE_KIND_MISMATCH")
    report_sha = save_new(destination / "historical-price-only-report.json", result)
    receipt = {
        "status": "PRIVATE_ORDER022_REPLAY_COMPLETED_NOT_SCIENTIFICALLY_QUALIFIED",
        "result_report_sha256": report_sha,
        "frozen_manifest_sha256": freeze_receipt["manifest_sha256"],
        "verified_private_archive_count": len(originals),
        "source_manifest_sha256": LEGACY_MANIFEST_SHA256,
        "source_index_present_and_pinned": source_index is not None,
        "scope": "PRICE_VOLUME_PARTIAL_ONLY_NO_QUALIFIED_SIGNAL",
        "historical_pit": "HISTORICAL_REPLAY_PIT_UNVERIFIED",
        "market_requests": 0, "publishable": False, "stage05": "FULL_HOLD",
        "output_directory": str(destination),
    }
    save_new(destination / "private-run-receipt.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description="One-shot private 010-B import; no network")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--out", required=True)
    opts = parser.parse_args(argv)
    try:
        status = perform(opts.source_root, opts.out)
    except (ResearchBlocked, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED_OFFLINE", "reason": str(exc),
                          "market_requests": 0}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(status, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
