from typing import Optional, List, Literal
from pydantic import BaseModel

class GitHubScanRequest(BaseModel): #This is where our input repo url is stored
    repo_url: str
class Finding(BaseModel): #This is the findings of the scanner. Which rule a potential vuln violated, severity, msg, optional location
    rule_id: str
    severity: Literal["low", "medium", "high"]
    message: str
    location: Optional[int] = None

class ScanResponse(BaseModel): #Return list of findings
    findings: List[Finding]

