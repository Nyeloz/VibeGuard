from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import List, Optional, Tuple, Literal

from models.contracts import Finding

SNIPPET_LIMIT = 160

@dataclass(frozen=True)
class Rule:
    id: str
    severity: Literal["low", "medium", "high"]
    message: str
    pattern: re.Pattern[str]
    file_exts: Optional[Tuple[str, ...]] = None

def _rule(
    rule_id: str,
    severity: Literal["low", "medium", "high"],
    message: str,
    pattern: str,
    file_exts: Optional[Tuple[str, ...]] = None,
    *,
    ignore_case: bool = True,
) -> Rule:
    flags = re.IGNORECASE if ignore_case else 0
    return Rule(rule_id, severity, message, re.compile(pattern, flags), file_exts)

# Language-agnostic rules (apply to any file)
RULES: Tuple[Rule, ...] = (
    _rule(
        "PRIVATE_KEY",
        "high",
        "Private key material detected",
        r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|PRIVATE) PRIVATE KEY-----",
        None,
    ),
    _rule(
        "AWS_ACCESS_KEY",
        "high",
        "Possible AWS access key detected",
        r"\bAKIA[0-9A-Z]{16}\b",
        None,
        ignore_case=False,
    ),
    _rule(
        "BASIC_AUTH_URL",
        "medium",
        "Credentials embedded in URL",
        r"https?://[^/\s:@]+:[^/\s:@]+@",
        None,
    ),
    _rule(
        "HARDCODED_SECRET",
        "medium",
        "Possible hardcoded secret detected",
        r"\b(?:api|secret|token|key|password|passwd)\b[^=\n]*=\s*['\"][^'\"\s]{8,}['\"]",
        None,
    ),
    # Python-specific rules
    _rule(
        "PY_SHELL_TRUE",
        "high",
        "subprocess with shell=True can enable command injection",
        r"\bshell\s*=\s*True\b",
        (".py", ".pyw"),
    ),
    _rule(
        "PY_EVAL",
        "high",
        "Use of eval() can lead to code execution vulnerabilities",
        r"\beval\s*\(",
        (".py", ".pyw"),
    ),
    _rule(
        "PY_EXEC",
        "high",
        "Use of exec() can lead to code execution vulnerabilities",
        r"\bexec\s*\(",
        (".py", ".pyw"),
    ),
    _rule(
        "PY_WEAK_HASH",
        "medium",
        "Weak hash function (md5/sha1) detected",
        r"\b(md5|sha1)\s*\(",
        (".py", ".pyw"),
    ),
    # JavaScript / TypeScript rules
    _rule(
        "JS_EVAL",
        "high",
        "Use of eval() can lead to code execution vulnerabilities",
        r"\beval\s*\(",
        (".js", ".jsx", ".ts", ".tsx"),
    ),
    _rule(
        "JS_NEW_FUNCTION",
        "high",
        "Use of new Function() can lead to code execution vulnerabilities",
        r"\bnew\s+Function\s*\(",
        (".js", ".jsx", ".ts", ".tsx"),
    ),
    _rule(
        "JS_CHILD_PROCESS_EXEC",
        "high",
        "child_process exec can enable command injection",
        r"\bchild_process\.(?:exec|execSync)\s*\(",
        (".js", ".jsx", ".ts", ".tsx"),
    ),
    _rule(
        "JS_SHELL_TRUE",
        "high",
        "spawn/exec with shell:true can enable command injection",
        r"\bshell\s*:\s*true\b",
        (".js", ".jsx", ".ts", ".tsx"),
    ),
    # Java rules
    _rule(
        "JAVA_RUNTIME_EXEC",
        "high",
        "Runtime.exec can enable command injection",
        r"\bRuntime\.getRuntime\(\)\.exec\s*\(",
        (".java",),
    ),
    _rule(
        "JAVA_PROCESS_BUILDER",
        "high",
        "ProcessBuilder can execute system commands",
        r"\bnew\s+ProcessBuilder\s*\(",
        (".java",),
    ),
    _rule(
        "JAVA_DESERIALIZATION",
        "medium",
        "ObjectInputStream can be unsafe with untrusted data",
        r"\bnew\s+ObjectInputStream\s*\(",
        (".java",),
    ),
    _rule(
        "JAVA_WEAK_HASH",
        "medium",
        "Weak hash function (MD5/SHA1) detected",
        r"\bMessageDigest\.getInstance\s*\(\s*\"(?:MD5|SHA1)\"\s*\)",
        (".java",),
        ignore_case=False,
    ),
)

SECRET_RULE_IDS = {
    "PRIVATE_KEY",
    "AWS_ACCESS_KEY",
    "BASIC_AUTH_URL",
    "HARDCODED_SECRET",
}

SECRET_RULES: Tuple[Rule, ...] = tuple(
    rule for rule in RULES if rule.id in SECRET_RULE_IDS
)

def scan_text(path: str, text: str, rules: Optional[Tuple[Rule, ...]] = None) -> List[Finding]:
    findings: List[Finding] = []
    ext = os.path.splitext(path)[1].lower()
    active_rules = rules or RULES

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        for rule in active_rules:
            if rule.file_exts and ext not in rule.file_exts:
                continue
            if rule.pattern.search(line):
                snippet = line.strip()
                if len(snippet) > SNIPPET_LIMIT:
                    snippet = snippet[:SNIPPET_LIMIT] + "..."
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity=rule.severity,
                        message=rule.message,
                        location=line_no,
                        path=path,
                        line=line_no,
                        snippet=snippet,
                    )
                )
                break

    return findings
