# Shared contract between API (Person A) and Scanner (Person B)
# DO NOT change fields without updating CONTRACT.md

from typing import Optional, List, Literal
from pydantic import BaseModel


Severity = Literal["low", "medium", "high"]


class ScanResponse(BaseModel):
    rule_id: str
    severity: Severity
    message: str
    line: Optional[int] = None
    snippet: Optional[str] = None


class GitHubScanRequest(BaseModel):
    findings: List[ScanResponse]
