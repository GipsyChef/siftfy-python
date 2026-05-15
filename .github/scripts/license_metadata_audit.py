#!/usr/bin/env python3
# ruff: noqa: E501,I001,UP035
"""Audit open-source license files and package metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


LICENSE_FILES = ("LICENSE", "LICENSE.md", "COPYING", "COPYING.md")
COMMON_SPDX = {
    "0BSD",
    "AGPL-3.0-only",
    "AGPL-3.0-or-later",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "GPL-2.0-only",
    "GPL-2.0-or-later",
    "GPL-3.0-only",
    "GPL-3.0-or-later",
    "ISC",
    "LGPL-2.1-only",
    "LGPL-2.1-or-later",
    "LGPL-3.0-only",
    "LGPL-3.0-or-later",
    "MIT",
    "MPL-2.0",
    "Unlicense",
}

SPDX_TOKEN = re.compile(r"^[A-Za-z0-9-.+]+$")
LICENSE_EXPR = re.compile(r"^[A-Za-z0-9-.+() ]+(?:\s+(?:AND|OR|WITH)\s+[A-Za-z0-9-.+() ]+)*$")


@dataclass
class Finding:
    severity: str
    check: str
    path: str
    message: str


def license_files(root: Path) -> list[Path]:
    return [root / name for name in LICENSE_FILES if (root / name).exists()]


def classify_license_value(value: object) -> tuple[str, str]:
    if not isinstance(value, str):
        return "blocker", "missing or invalid license metadata"
    value = value.strip()
    if not value or value.upper() in {"TODO", "TBD", "UNKNOWN"}:
        return "blocker", "missing or invalid license metadata"
    if value in COMMON_SPDX:
        return "ok", f"license metadata present: {value}"
    if SPDX_TOKEN.match(value) or LICENSE_EXPR.match(value):
        return "warn", f"unrecognized license expression; verify SPDX identifier before release: {value}"
    return "blocker", "missing or invalid license metadata"


def read_json(path: Path) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def read_toml(path: Path) -> dict[str, object] | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def add_license_value(findings: list[Finding], check: str, path: str, value: object) -> None:
    severity, message = classify_license_value(value)
    findings.append(Finding(severity, check, path, message))


def audit_package_json(root: Path, findings: list[Finding]) -> None:
    path = root / "package.json"
    if not path.exists():
        return
    data = read_json(path)
    if data is None:
        findings.append(Finding("blocker", "package_json_parse", "package.json", "package.json is not valid JSON"))
        return
    add_license_value(findings, "package_license", "package.json", data.get("license"))
    for key in ("name", "description", "repository"):
        if data.get(key):
            findings.append(Finding("ok", f"package_{key}", "package.json", f"{key} present"))
        else:
            findings.append(Finding("warn", f"package_{key}", "package.json", f"missing {key} metadata"))


def audit_pyproject(root: Path, findings: list[Finding]) -> None:
    path = root / "pyproject.toml"
    if not path.exists():
        return
    data = read_toml(path)
    if data is None:
        findings.append(Finding("blocker", "pyproject_parse", "pyproject.toml", "pyproject.toml is not valid TOML"))
        return
    project = data.get("project")
    poetry = data.get("tool", {})
    poetry_project = poetry.get("poetry", {}) if isinstance(poetry, dict) else {}
    if isinstance(project, dict):
        license_value = project.get("license")
        if isinstance(license_value, dict):
            license_value = license_value.get("text") or license_value.get("file")
        add_license_value(findings, "pyproject_license", "pyproject.toml", license_value)
    elif isinstance(poetry_project, dict):
        add_license_value(findings, "poetry_license", "pyproject.toml", poetry_project.get("license"))
    else:
        findings.append(Finding("warn", "pyproject_project", "pyproject.toml", "no [project] or [tool.poetry] metadata detected"))


def audit_cargo(root: Path, findings: list[Finding]) -> None:
    path = root / "Cargo.toml"
    if not path.exists():
        return
    data = read_toml(path)
    if data is None:
        findings.append(Finding("blocker", "cargo_parse", "Cargo.toml", "Cargo.toml is not valid TOML"))
        return
    package = data.get("package")
    if isinstance(package, dict):
        add_license_value(findings, "cargo_license", "Cargo.toml", package.get("license"))
        if not package.get("description"):
            findings.append(Finding("warn", "cargo_description", "Cargo.toml", "missing package description"))
    else:
        findings.append(Finding("warn", "cargo_package", "Cargo.toml", "no [package] metadata detected"))


def audit_composer(root: Path, findings: list[Finding]) -> None:
    path = root / "composer.json"
    if not path.exists():
        return
    data = read_json(path)
    if data is None:
        findings.append(Finding("blocker", "composer_parse", "composer.json", "composer.json is not valid JSON"))
        return
    license_value = data.get("license")
    if isinstance(license_value, list):
        severities = [classify_license_value(item)[0] for item in license_value]
        if "blocker" in severities:
            findings.append(Finding("blocker", "composer_license", "composer.json", "missing or invalid license metadata"))
        elif "warn" in severities:
            findings.append(Finding("warn", "composer_license", "composer.json", "unrecognized license expression; verify SPDX identifiers before release"))
        else:
            findings.append(Finding("ok", "composer_license", "composer.json", "license metadata present"))
    else:
        add_license_value(findings, "composer_license", "composer.json", license_value)


def audit_gemspec(root: Path, findings: list[Finding]) -> None:
    for path in root.glob("*.gemspec"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"\.licenses?\s*=\s*\[?['\"][A-Za-z0-9-.+]+['\"]", text):
            findings.append(Finding("ok", "gemspec_license", path.name, "license metadata present"))
        else:
            findings.append(Finding("blocker", "gemspec_license", path.name, "missing license metadata"))


def audit(root: Path) -> dict[str, object]:
    root = root.resolve()
    findings: list[Finding] = []

    found_license_files = license_files(root)
    if found_license_files:
        for path in found_license_files:
            rel = str(path.relative_to(root))
            text = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"\b(todo|tbd|choose a license|add license)\b", text, re.I):
                findings.append(Finding("blocker", "license_placeholder", rel, "license file contains unresolved placeholder text"))
            elif len(text.strip()) < 100:
                findings.append(Finding("warn", "license_file", rel, "license file is unusually short; verify official text"))
            else:
                findings.append(Finding("ok", "license_file", rel, "license file present"))
    else:
        findings.append(Finding("blocker", "license_file", ".", "missing license file"))

    audit_package_json(root, findings)
    audit_pyproject(root, findings)
    audit_cargo(root, findings)
    audit_composer(root, findings)
    audit_gemspec(root, findings)

    if not any((root / name).exists() for name in ("package.json", "pyproject.toml", "Cargo.toml", "composer.json")) and not list(root.glob("*.gemspec")):
        findings.append(Finding("info", "package_metadata", ".", "no recognized package metadata found"))

    return report(root, findings)


def report(root: Path, findings: Iterable[Finding]) -> dict[str, object]:
    finding_list = list(findings)
    counts: dict[str, int] = {}
    for finding in finding_list:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    decision = "no-go" if counts.get("blocker") else "conditional" if counts.get("warn") else "go"
    return {
        "root": str(root),
        "decision": decision,
        "counts": counts,
        "findings": [asdict(finding) for finding in finding_list],
    }


def print_human(data: dict[str, object]) -> None:
    print(f"License metadata readiness: {data['decision']}")
    print(f"Repository: {data['root']}")
    print(f"Counts: {data['counts']}")
    print()
    for finding in data["findings"]:  # type: ignore[index]
        print(f"[{finding['severity']}] {finding['check']} {finding['path']} - {finding['message']}")


def should_fail(data: dict[str, object], fail_on: str) -> bool:
    counts = data["counts"]  # type: ignore[assignment]
    if fail_on == "none":
        return False
    if fail_on == "warn":
        return bool(counts.get("blocker") or counts.get("warn"))  # type: ignore[union-attr]
    return bool(counts.get("blocker"))  # type: ignore[union-attr]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="repository path")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument("--fail-on", choices=("none", "blocker", "warn"), default="none", help="exit nonzero at this severity")
    args = parser.parse_args()

    data = audit(Path(args.repo))
    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print_human(data)
    return 1 if should_fail(data, args.fail_on) else 0


if __name__ == "__main__":
    sys.exit(main())
