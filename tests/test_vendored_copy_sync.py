"""Guards against silent drift between the standalone engine/repositories/
providers packages and their vendored copies under
custom_components/portfolio_engine/ (see PROJECT_STATUS.md - vendored for
self-contained HACS/HA packaging, since these aren't published to PyPI).

Synchronization between the two copies is otherwise entirely manual, by
convention - every fix touching these directories this project has made
required hand-editing both copies. This test makes that convention
mechanically enforced instead of hoped-for: it walks every .py file in the
three standalone packages and asserts its vendored counterpart exists and
is content-identical, modulo the one known, deliberate difference (a
cross-package `from engine...` import becomes `from ..engine...` inside
the vendored tree, since vendored providers/repositories sit one level
deeper, under custom_components.portfolio_engine).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
VENDORED_ROOT = REPO_ROOT / "custom_components" / "portfolio_engine"

#: Standalone-only files with no vendored counterpart, by design - the HA
#: integration doesn't need them. Paths relative to the package they live in.
STANDALONE_ONLY = {
    ("repositories", "in_memory_snapshot_repository.py"),
}

PACKAGES = ["engine", "providers", "repositories"]


def _normalize(text: str) -> list[str]:
    # The vendored copy's only intentional difference: a top-level
    # "from engine." import becomes "from ..engine." one level deeper.
    # Normalize that one known substitution, plus line-ending differences,
    # before comparing - anything else that differs is real drift.
    return [line.replace("from ..engine.", "from engine.") for line in text.splitlines()]


def _all_py_files(package_dir: Path) -> list[Path]:
    return sorted(p for p in package_dir.rglob("*.py") if "__pycache__" not in p.parts)


def test_every_standalone_file_has_a_vendored_counterpart():
    missing = []
    for package in PACKAGES:
        package_dir = REPO_ROOT / package
        for path in _all_py_files(package_dir):
            rel = path.relative_to(REPO_ROOT / package)
            if (package, str(rel)) in STANDALONE_ONLY:
                continue
            vendored_path = VENDORED_ROOT / package / rel
            if not vendored_path.exists():
                missing.append(str(vendored_path.relative_to(REPO_ROOT)))
    assert not missing, f"Missing vendored counterparts: {missing}"


def test_vendored_copies_match_standalone_content_modulo_known_import_substitution():
    mismatches = []
    for package in PACKAGES:
        package_dir = REPO_ROOT / package
        for path in _all_py_files(package_dir):
            rel = path.relative_to(REPO_ROOT / package)
            if (package, str(rel)) in STANDALONE_ONLY:
                continue
            vendored_path = VENDORED_ROOT / package / rel
            if not vendored_path.exists():
                continue  # reported separately by the existence test above

            standalone_lines = _normalize(path.read_text(encoding="utf-8"))
            vendored_lines = _normalize(vendored_path.read_text(encoding="utf-8"))
            if standalone_lines != vendored_lines:
                mismatches.append(f"{package}/{rel}")

    assert not mismatches, (
        f"Vendored copy has drifted from its standalone source (beyond the "
        f"known 'from engine.' -> 'from ..engine.' substitution): {mismatches}"
    )
