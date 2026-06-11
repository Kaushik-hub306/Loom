"""IntegrityGuard — ensures rule store file hasn't been tampered with."""

import hashlib
import hmac
from pathlib import Path


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
