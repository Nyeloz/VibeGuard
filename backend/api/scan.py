#endpoint

from fastapi import APIRouter, HTTPException
from models.contracts import GitHubScanRequest, ScanResponse, SourceFile
from scanner.engine import scan_source_files
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import io
import os
import zipfile

class InvalidGitHubRepoUrl(ValueError):
    pass

class RepoFetchError(RuntimeError):
    pass

USER_AGENT = "vibeguard/0.1"
MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".next",
    "node_modules",
    "dist",
    "build",
    "target",
    "coverage",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
}

scan_router = APIRouter()
@scan_router.post("/github", response_model=ScanResponse)
def scan_GitHub(request: GitHubScanRequest):

    repo_url = request.repo_url

    try:
        normalized_url = normalize_Url(repo_url)
    except InvalidGitHubRepoUrl as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        files = fetch_github_files(normalized_url)
    except RepoFetchError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch repository")

    findings = scan_source_files(files)
    return { "findings": findings}

def normalize_Url(repo_url: str) -> str:
    
    if not repo_url or not repo_url.strip():
        raise InvalidGitHubRepoUrl("Empty URL")

    url = repo_url.strip()

    if not url.startswith(("https://")): #if url doesn't start with https://, add it
        url = "https://" + url

    parsed = urlparse(url)

    if parsed.netloc != "github.com":#github repo input only
        raise InvalidGitHubRepoUrl("Only github.com repo URLs are supported")

    if parsed.query or parsed.fragment: # Reject query strings or fragments
        raise InvalidGitHubRepoUrl("Invalid GitHub repo URL")

    path = parsed.path.rstrip("/") #Normalize path
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.lstrip("/").split("/")

    # Must be exactly /owner/repo
    if len(parts) != 2:
        raise InvalidGitHubRepoUrl("URL must be a GitHub repository root (https://github.com/owner/repo)")
    owner, repo = parts

    if not owner or not repo:
        raise InvalidGitHubRepoUrl("Invalid GitHub repo URL")

    return f"https://github.com/{owner}/{repo}"

def fetch_github_files(repo_url: str) -> list[SourceFile]:
    owner, repo = parse_owner_repo(repo_url)
    zip_bytes = download_repo_zip(owner, repo)
    return extract_text_files(zip_bytes)

def parse_owner_repo(repo_url: str) -> tuple[str, str]:
    parsed = urlparse(repo_url)
    path = parsed.path.strip("/")
    parts = path.split("/")
    if len(parts) != 2:
        raise RepoFetchError("Invalid GitHub repo URL format")
    return parts[0], parts[1]

def download_repo_zip(owner: str, repo: str) -> bytes:
    branches = ("main", "master")
    last_error: str | None = None

    for branch in branches:
        url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"
        req = Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urlopen(req, timeout=30) as resp:
                length = resp.headers.get("Content-Length")
                if length and int(length) > MAX_ZIP_BYTES:
                    raise RepoFetchError("Repository zip is too large to scan")
                data = resp.read(MAX_ZIP_BYTES + 1)
                if len(data) > MAX_ZIP_BYTES:
                    raise RepoFetchError("Repository zip is too large to scan")
                return data
        except HTTPError as e:
            if e.code == 404:
                last_error = f"Repository or branch not found (tried {branch})"
                continue
            if e.code == 403:
                raise RepoFetchError("GitHub blocked the request or rate limit exceeded")
            raise RepoFetchError(f"GitHub download failed with status {e.code}")
        except URLError:
            raise RepoFetchError("Could not reach GitHub")

    raise RepoFetchError(last_error or "Unable to download repository")

def extract_text_files(zip_bytes: bytes) -> list[SourceFile]:
    files: list[SourceFile] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            rel_path = normalize_zip_path(info.filename)
            if not rel_path:
                continue
            if should_skip_path(rel_path):
                continue
            if info.file_size > MAX_FILE_BYTES:
                continue
            with zf.open(info) as f:
                data = f.read()
            if looks_binary(data):
                continue
            text = data.decode("utf-8", errors="ignore")
            files.append(SourceFile(path=rel_path, content=text))

    return files

def normalize_zip_path(path: str) -> str:
    if "/" in path:
        _, rest = path.split("/", 1)
        return rest
    return path

def should_skip_path(path: str) -> bool:
    parts = [p for p in path.split("/") if p]
    for part in parts:
        if part in IGNORED_DIRS:
            return True
    return False

def looks_binary(data: bytes) -> bool:
    if not data:
        return False
    if b"\x00" in data:
        return True
    text_chars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(32, 127)))
    nontext = sum(1 for b in data if b not in text_chars)
    return nontext / len(data) > 0.3
