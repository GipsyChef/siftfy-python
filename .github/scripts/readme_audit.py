#!/usr/bin/env python3
# ruff: noqa: E501,I001,UP035
"""Audit README quality for first-user open-source readiness."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


README_NAMES = ("README.md", "README.rst", "README")

PLACEHOLDERS = [
    "one-sentence description",
    "short project description",
    "add the fastest working install command",
    "add ecosystem-specific install command",
    "add setup commands",
    "describe whether this project is",
    "describe the visible output",
    "add an exact official license",
    "todo",
    "tbd",
]

REQUIRED_SIGNALS = [
    ("purpose", re.compile(r"\b(what this project|overview|purpose|about|does|is a|is an)\b", re.I), "explain what the project is"),
    ("problem", re.compile(r"\b(problem|solves|why|use case|pain|workflow|for teams|for developers)\b", re.I), "explain what problem it solves"),
    ("status", re.compile(r"\b(status|stable|experimental|production|preview|archived|alpha|beta)\b", re.I), "document project status"),
    ("requirements", re.compile(r"\b(requirements|prerequisites|dependencies|supported|compatibility|platform)\b", re.I), "document prerequisites and compatibility"),
    ("install", re.compile(r"\b(install|installation|setup)\b", re.I), "document installation"),
    ("quickstart", re.compile(r"\b(quickstart|quick start|get started|getting started)\b", re.I), "document the shortest working path"),
    ("usage", re.compile(r"\b(usage|example|examples|api|cli)\b", re.I), "show a minimal real usage example"),
    ("expected_result", re.compile(r"\b(expected|output|result|you should see|localhost|http://|https://)\b", re.I), "describe expected output or behavior"),
    ("development", re.compile(r"\b(development|contributing|test|tests|lint|build)\b", re.I), "document development validation commands"),
    ("support", re.compile(r"\b(support|questions|issues|bugs|feature requests|discussion)\b", re.I), "document support and issue paths"),
    ("security", re.compile(r"\b(security|vulnerability|vulnerabilities|disclosure)\b", re.I), "document vulnerability reporting or link SECURITY.md"),
    ("license", re.compile(r"\b(license|licence|spdx)\b", re.I), "document license"),
]


@dataclass
class Finding:
    severity: str
    check: str
    path: str
    message: str


def find_readme(root: Path) -> Path | None:
    for name in README_NAMES:
        path = root / name
        if path.exists():
            return path
    return None


def line_number(text: str, needle: str) -> int:
    offset = text.lower().find(needle.lower())
    if offset < 0:
        return 1
    return text[:offset].count("\n") + 1


def has_code_block(text: str) -> bool:
    return "```" in text or "::\n" in text


def has_shell_command(text: str) -> bool:
    return bool(re.search(r"(?m)^\s*(?:\$ |npm |pnpm |yarn |python|pip |go |cargo |make |docker |git clone|curl )", text))


def audit(root: Path) -> dict[str, object]:
    root = root.resolve()
    findings: list[Finding] = []
    readme = find_readme(root)
    if not readme:
        findings.append(Finding("blocker", "readme", ".", "missing README"))
        return report(root, findings)

    rel = str(readme.relative_to(root))
    text = readme.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()

    if len(text.strip()) < 600:
        findings.append(Finding("warn", "readme_depth", rel, "README is very short for a public project"))
    else:
        findings.append(Finding("ok", "readme_depth", rel, "README has substantive content"))

    title_match = re.search(r"(?m)^\s*#\s+\S+", text)
    if title_match:
        findings.append(Finding("ok", "title", f"{rel}:{text[:title_match.start()].count(chr(10)) + 1}", "top-level title present"))
    else:
        findings.append(Finding("warn", "title", rel, "missing top-level project title"))

    for phrase in PLACEHOLDERS:
        if re.search(rf"\b{re.escape(phrase)}\b", lower):
            findings.append(Finding("blocker", "placeholder", f"{rel}:{line_number(text, phrase)}", f"unresolved placeholder: {phrase}"))

    for check, pattern, message in REQUIRED_SIGNALS:
        if pattern.search(text):
            findings.append(Finding("ok", check, rel, "present"))
        else:
            severity = "blocker" if check in {"purpose", "install", "quickstart", "license"} else "warn"
            findings.append(Finding(severity, check, rel, message))

    if has_code_block(text):
        findings.append(Finding("ok", "examples", rel, "code block present"))
    else:
        findings.append(Finding("warn", "examples", rel, "README should include copy-pasteable commands or examples"))

    if has_shell_command(text):
        findings.append(Finding("ok", "commands", rel, "command-like setup or usage examples present"))
    else:
        findings.append(Finding("warn", "commands", rel, "README should include concrete commands"))

    if (root / "SECURITY.md").exists() and "security" not in lower:
        findings.append(Finding("warn", "security_link", rel, "README should link or mention SECURITY.md"))

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
    print(f"README readiness: {data['decision']}")
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
