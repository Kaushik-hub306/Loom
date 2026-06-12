"""IntegrityGuard — ensures rule store file hasn't been tampered with."""

import hashlib
import hmac
import json
from pathlib import Path


def compute_and_store(store: Path) -> None:
    store = Path(store)
    checksums = {}
    for name in ["rules.json", "history.jsonl", "conventions.md"]:
        fpath = store / name
        if fpath.exists():
            h = hashlib.sha256(fpath.read_bytes()).hexdigest()
            checksums[name] = h
    (store / "integrity.json").write_text(json.dumps(checksums, indent=2))


def verify_store_integrity(store: Path) -> tuple[bool, str]:
    store = Path(store)
    cs_path = store / "integrity.json"
    if not cs_path.exists():
        return True, "No integrity file — nothing to verify"
    try:
        stored = json.loads(cs_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return False, f"Failed to read integrity file: {e}"

    for name, expected_hash in stored.items():
        fpath = store / name
        if not fpath.exists():
            return False, f"Missing file: {name}"
        actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if not hmac.compare_digest(expected_hash, actual):
            return False, f"Tampered: {name} (hash mismatch)"
    return True, "All checksums match"


class IntegrityGuard:
    """Validates integrity of the rules file."""

    def __init__(self, checksum_path: Path | None = None):
        self.checksum_path = checksum_path

    def compute_hash(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def sign(self, rules_path: Path):
        data = rules_path.read_text()
        h = self.compute_hash(data)
        cs_path = self.checksum_path or rules_path.parent / ".rules.sha256"
        cs_path.write_text(h)

    def verify(self, rules_path: Path) -> bool:
        cs_path = self.checksum_path or rules_path.parent / ".rules.sha256"
        if not cs_path.exists():
            return True
        expected = cs_path.read_text().strip()
        actual = self.compute_hash(rules_path.read_text())
        return hmac.compare_digest(expected, actual)
