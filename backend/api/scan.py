#endpoint

from fastapi import APIRouter
from models.contracts import GitHubScanRequest, ScanResponse

scan_router = APIRouter()

@scan_router.post("/github", response_model=ScanResponse)
def scan_github(request: GitHubScanRequest):
    return { "findings": []}
