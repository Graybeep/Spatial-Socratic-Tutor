"""CLAUDE.md §1.8: no new dependencies after the end of week 2 (2026-09-17).

A rule that lives only in a markdown file is kept by memory, and one person at
the end of week 3 with a demo to finish is exactly the memory that fails. So the
freeze is two tripwires:

- the declared set is closed: adding a line to requirements.txt or package.json
  fails here, and the fix is not to edit FROZEN_* below but to not add it;
- the code cannot quietly depend on something undeclared that happens to be
  installed on this laptop and not on the demo machine.

Versions are not asserted, only names. Bumping a pin to fix a security or
install problem is maintenance; a new name is a new dependency.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FROZEN_PYTHON = {"fastapi", "uvicorn", "pydantic", "httpx", "pytest"}
FROZEN_CLIENT = {
    "react", "react-dom",
    "@types/react", "@types/react-dom", "@vitejs/plugin-react", "typescript", "vite",
}

#: Our own top-level packages.
LOCAL = {"server", "build", "eval", "tests"}

#: Imported, deliberately not declared. Each needs a reason a reader can check.
UNDECLARED_ON_PURPOSE = {
    # build/chunk.py PdfChunker imports it lazily and exits with an explanation
    # if absent. The chapter is ingested from HTML; no PDF path is exercised.
    "fitz",
}


def _requirement_names() -> set[str]:
    names = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.add(re.split(r"[\[=<>!~ ;]", line, maxsplit=1)[0].lower())
    return names


def _client_package() -> dict:
    return json.loads((ROOT / "client" / "package.json").read_text(encoding="utf-8"))


def _python_imports() -> dict[str, set[str]]:
    """top-level module -> files importing it, from the AST (not from docstrings)."""
    found: dict[str, set[str]] = {}
    for pkg in LOCAL:
        for path in (ROOT / pkg).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    mods = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    mods = [node.module]
                else:
                    continue
                for mod in mods:
                    found.setdefault(mod.split(".")[0], set()).add(
                        path.relative_to(ROOT).as_posix()
                    )
    return found


def test_requirements_are_the_frozen_set():
    assert _requirement_names() == FROZEN_PYTHON, (
        "requirements.txt changed after the §1.8 dependency freeze (2026-09-17)"
    )


def test_client_packages_are_the_frozen_set():
    pkg = _client_package()
    declared = set(pkg.get("dependencies", {})) | set(pkg.get("devDependencies", {}))
    assert declared == FROZEN_CLIENT, (
        "client/package.json changed after the §1.8 dependency freeze (2026-09-17)"
    )


def test_every_version_is_pinned_exactly():
    """A caret range lets the demo machine install something the suite never saw."""
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            assert "==" in line, f"unpinned requirement: {line}"
    pkg = _client_package()
    for section in ("dependencies", "devDependencies"):
        for name, version in pkg.get(section, {}).items():
            assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"unpinned {name}: {version}"


def test_python_code_imports_nothing_undeclared():
    allowed = set(sys.stdlib_module_names) | LOCAL | FROZEN_PYTHON | UNDECLARED_ON_PURPOSE
    stray = {m: sorted(f) for m, f in _python_imports().items() if m not in allowed}
    assert not stray, f"imports outside the frozen dependency set: {stray}"


def test_the_undeclared_exceptions_are_still_real():
    """An exemption for an import that no longer exists is a hole with no reason."""
    imports = _python_imports()
    assert UNDECLARED_ON_PURPOSE <= set(imports)


def test_client_code_imports_nothing_undeclared():
    declared = FROZEN_CLIENT
    # Anchored to statement starts: a comment reading "from 'x'" is not an import.
    spec = re.compile(
        r"""^\s*(?:import|export)\b(?:[^'";]*?\bfrom)?\s*['"]([^'"]+)['"]""", re.M
    )
    stray = {}
    for path in [*(ROOT / "client" / "src").rglob("*.ts*"), ROOT / "client" / "vite.config.ts"]:
        for target in spec.findall(path.read_text(encoding="utf-8")):
            if target.startswith("."):
                continue
            parts = target.split("/")
            name = "/".join(parts[:2]) if target.startswith("@") else parts[0]
            if name not in declared:
                stray.setdefault(name, []).append(path.relative_to(ROOT).as_posix())
    assert not stray, f"client imports outside the frozen dependency set: {stray}"
