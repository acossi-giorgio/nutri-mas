import csv
import os
from pathlib import Path
import tempfile


def read_csv(path: str, encoding: str = "utf-8") -> list[dict]:
    """Read a CSV as dictionaries, returning an empty list if it is missing."""
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding=encoding) as f:
        return list(csv.DictReader(f))


def write_csv(
    path: str, fieldnames: list[str], rows: list[dict], encoding: str = "utf-8"
) -> None:
    """Write rows atomically using a stable schema and ordering."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stable_rows = sorted(
        rows,
        key=lambda row: tuple(str(row.get(field, "")) for field in fieldnames),
    )
    file_descriptor, temporary_path = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(file_descriptor, "w", newline="", encoding=encoding) as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(stable_rows)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, destination)
    except Exception:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise
