"""Shared helpers for the web build scripts (repo root, source revision).

Every script in web/scripts resolves the repository from its own location,
so it runs from any working directory with only NumPy installed.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# These scripts print physics symbols (sigma, subscripts). A Windows console --
# and any piped stdout on Windows -- defaults to the ANSI code page and raises
# UnicodeEncodeError on them, so force UTF-8 wherever the stream allows it.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError, ValueError):
        pass


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                             capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout


def spectral_sources() -> list[tuple[str, bytes]]:
    """Every spectral/**/*.py as (repo-relative posix path, bytes), sorted by path.

    Exactly what the web archive packs (build_py_archive.py adds only the
    generated spectral/_build_info.py), and what source_revision() hashes.
    """
    src = REPO_ROOT / "spectral"
    files = sorted(
        (p.relative_to(REPO_ROOT).as_posix(), p)
        for p in src.rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "_build_info.py"
    )
    return [(rel, p.read_bytes()) for rel, p in files]


def sources_digest() -> str:
    """sha256 over the sorted (path, bytes) list of spectral_sources()."""
    h = hashlib.sha256()
    for rel, data in spectral_sources():
        name = rel.encode("utf-8")
        h.update(len(name).to_bytes(8, "little") + name)
        h.update(len(data).to_bytes(8, "little") + data)
    return h.hexdigest()


def source_revision() -> str:
    """The revision of the Python sources the web build and references use.

    `git rev-parse HEAD` when every spectral/**/*.py matches HEAD (git
    reports no modified, staged, deleted, untracked or ignored .py file
    under spectral/). Otherwise HEAD + "-dirty-" + sources_digest()[:12],
    so two builds from different uncommitted sources never share a
    revision: native references and the archive agree only when their
    sources match. Other changes (web/, gui/, docs) do not affect it; they
    cannot change a computed result.
    """
    head = _git("rev-parse", "HEAD")
    if head is None:
        return "unknown-" + sources_digest()[:12]
    rev = head.strip()
    status = _git("status", "--porcelain", "--untracked-files=all", "--ignored",
                  "--", "spectral")
    if status is None or any(_is_source(p) for line in status.splitlines()
                             for p in line[3:].split(" -> ")):
        rev += "-dirty-" + sources_digest()[:12]
    return rev


def _is_source(path: str) -> bool:
    path = path.strip().strip('"')
    return (path.endswith(".py") and "__pycache__" not in path
            and not path.endswith("_build_info.py"))


def use_revision(revision: str) -> None:
    """Make the native bridge report (and key its cache on) this revision."""
    import spectral.browser as browser
    browser.SOURCE_REVISION = revision
