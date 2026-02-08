#endpoint

from fastapi import APIRouter
from models.contracts import Finding, GitHubScanRequest, ScanResponse
import re




scan_router = APIRouter()

@scan_router.post("/github", response_model=ScanResponse)
def scan_github(request: GitHubScanRequest):

    repo_url = request.repo_url

    return { "findings": []}
