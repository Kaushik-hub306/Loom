"""SHA-256 hash chain for the memory store — detect tampering on startup."""

import hashlib
import hmac
import json
from pathlib import Path


INTEGRITY_FILE = "integrity.json"


class IntegrityError(Exception):
    """Raised programmatically when a caller requires integrity to proceed."""


def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compute_chain_hash(store_path: Path) -> str:
    """Derive a combined hash from all tracked store files.

    Files hashed: rules.json, history.jsonl, conventions.md (if present).
    """
    hasher = hashlib.sha256()
    for name in ("rules.json", "history.jsonl", "conventions.md"):
        file_hash = _hash_file(store_path / name)
        hasher.update(file_hash.encode())
    return hasher.hexdigest()


def _read_integrity(store_path: Path) -> dict:
    """Read the stored integrity record, returning {} on any failure."""
    ipath = store_path / INTEGRITY_FILE
    if not ipath.exists():
        return {}
    try:
        return json.loads(ipath.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_integrity(store_path: Path, data: dict) -> None:
    store_path.mkdir(parents=True, exist_ok=True)
    (store_path / INTEGRITY_FILE).write_text(json.dumps(data, indent=2))


def compute_and_store(store_path: Path) -> str:
    """Compute the current chain hash and persist it as the latest entry."""
    chain_hash = _compute_chain_hash(store_path)
    record = _read_integrity(store_path)

    entries: list[dict] = record.get("chain", [])
    entries.append({
        "hash": chain_hash,
        "index": len(entries),
    })
    record["chain"] = entries

    # Keep only the latest + genesis entry to bound file size
    if len(entries) > 2:
        record["chain"] = [entries[0], entries[-1]]

    _write_integrity(store_path, record)
    return chain_hash


def verify_store_integrity(store_path: Path) -> tuple[bool, str]:
    """Check whether the store matches the last recorded integrity hash.

    Returns (valid: bool, message: str).
    Fresh stores (no integrity file) are treated as valid.
    """
    record = _read_integrity(store_path)
    chain = record.get("chain", [])
    if not chain:
        return True, "No integrity chain exists yet — store is fresh."

    expected = chain[-1]["hash"]
    actual = _compute_chain_hash(store_path)
    if not actual:
        return True, "Store is empty — nothing to verify."

    if not hmac.compare_digest(expected, actual):
        return False, (
            f"Integrity check FAILED. Expected hash {expected[:16]}… "
            f"but computed {actual[:16]}…. The memory store may have been tampered with."
        )
    return True, "Integrity check passed."
