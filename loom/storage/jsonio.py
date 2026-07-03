"""Safe JSON file I/O shared by every Loom store.

Three guarantees the naive ``Path.write_text`` / ``json.loads`` pattern
doesn't give you:

1. **Atomic writes** — data is written to a temp file in the same
   directory, fsync'd, then moved into place with ``os.replace`` (atomic
   on POSIX and Windows). A crash mid-write can never leave a truncated
   or half-written file behind.
2. **Advisory locking** — writers take an exclusive lock on a sidecar
   ``.lock`` file (``fcntl`` on POSIX, ``msvcrt`` on Windows) so two
   concurrent Loom processes can't interleave writes.
3. **Corruption-safe loads** — a malformed file is quarantined to
   ``<name>.corrupt-<timestamp>`` and reported to stderr instead of being
   silently treated as empty (which previously meant the next save would
   permanently destroy all prior data). Individually malformed entries
   are skipped with a warning; the good entries survive.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

__all__ = [
    "atomic_write_json",
    "atomic_write_text",
    "file_lock",
    "load_json_dict",
    "load_entries",
    "quarantine_corrupt_file",
]


# ── Locking ───────────────────────────────────────────────────────────

@contextmanager
def file_lock(path: Path) -> Iterator[None]:
    """Exclusive advisory lock on a sidecar lockfile next to *path*.

    Best-effort: on platforms/filesystems without locking support this
    degrades to a no-op rather than failing the write.
    """
    lock_path = Path(str(path) + ".lock")
    handle = None
    locked = False
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+")
        try:
            if os.name == "nt":  # pragma: no cover (Windows)
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)  # type: ignore[attr-defined]
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
        except OSError:
            locked = False
        yield
    finally:
        if handle is not None:
            if locked:
                try:
                    if os.name == "nt":  # pragma: no cover (Windows)
                        import msvcrt

                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                except OSError:
                    pass
            handle.close()


# ── Atomic writes ─────────────────────────────────────────────────────

def atomic_write_text(path: Path, content: str) -> None:
    """Write *content* to *path* atomically (temp file + fsync + rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def atomic_write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Serialize *data* and write it to *path* atomically, under a lock."""
    with file_lock(Path(path)):
        atomic_write_text(Path(path), json.dumps(data, indent=indent))


# ── Corruption-safe loads ─────────────────────────────────────────────

def quarantine_corrupt_file(path: Path, reason: str) -> Path | None:
    """Move a corrupt file aside (never delete it) and warn on stderr."""
    path = Path(path)
    if not path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        os.replace(path, backup)
    except OSError:
        return None
    print(
        f"[loom] WARNING: {path.name} was corrupt ({reason}). "
        f"The damaged file was preserved at {backup.name}; starting from "
        f"the last recoverable state.",
        file=sys.stderr,
    )
    return backup


def load_json_dict(path: Path) -> dict:
    """Load *path* as a JSON object.

    Returns ``{}`` when the file is missing. When the file is unreadable
    or not a JSON object, the damaged file is quarantined (moved aside,
    never deleted) so a subsequent save cannot destroy prior data, and
    ``{}`` is returned.
    """
    path = Path(path)
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[loom] WARNING: cannot read {path.name}: {e}", file=sys.stderr)
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        quarantine_corrupt_file(path, f"invalid JSON: {e}")
        return {}
    if not isinstance(data, dict):
        quarantine_corrupt_file(
            path, f"expected a JSON object, found {type(data).__name__}"
        )
        return {}
    return data


def load_entries(
    entries: Any,
    parse: Callable[[dict], T],
    *,
    source_name: str = "store",
) -> list[T]:
    """Parse a list of dict entries, skipping (not wiping) malformed ones.

    Every entry that fails to parse is reported to stderr and skipped;
    valid entries always survive. This is the antidote to the
    all-or-nothing load that previously erased entire stores.
    """
    result: list[T] = []
    if not isinstance(entries, list):
        if entries is not None:
            print(
                f"[loom] WARNING: {source_name}: expected a list of entries, "
                f"found {type(entries).__name__}; ignoring.",
                file=sys.stderr,
            )
        return result
    skipped = 0
    for entry in entries:
        if not isinstance(entry, dict):
            skipped += 1
            continue
        try:
            result.append(parse(entry))
        except (KeyError, TypeError, ValueError, AttributeError):
            skipped += 1
    if skipped:
        print(
            f"[loom] WARNING: {source_name}: skipped {skipped} malformed "
            f"entr{'y' if skipped == 1 else 'ies'} (kept {len(result)} valid).",
            file=sys.stderr,
        )
    return result
