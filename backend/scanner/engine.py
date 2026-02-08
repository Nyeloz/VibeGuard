from __future__ import annotations

from typing import Iterable, List

from models.contracts import Finding, SourceFile
from scanner.rules import SECRET_RULES, scan_text

MAX_FILE_CHARS = 200_000  # guardrail against very large files

def scan_source_files(files: Iterable[SourceFile]) -> List[Finding]:
    """
    Core scanner entrypoint.
    Expects pre-filtered, text-only files from the ingestion layer.
    """
    findings: List[Finding] = []

    for source in files:
        if not source.content:
            continue
        if len(source.content) > MAX_FILE_CHARS:
            # For large files, only scan high-confidence secret rules.
            findings.extend(scan_text(source.path, source.content, SECRET_RULES))
            continue
        findings.extend(scan_text(source.path, source.content))

    return findings
