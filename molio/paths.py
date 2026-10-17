"""Default local storage, preserving existing installations without moving data."""
from pathlib import Path


def default_project_dir(base=None):
    base = Path('.') if base is None else Path(base)
    current = base / 'work/molio'
    legacy = base / 'work/whatif'
    if not current.exists() and legacy.is_dir():
        return legacy
    return current
