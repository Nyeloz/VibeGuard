from __future__ import annotations
import os
import io
import tempfile
import zipfile
from typing import Optional, Tuple, List
import asyncio

import httpx

from models.contracts import InputRepository, SourceFile, FilesPayload, FilesMetadata, Stats

# Exceptions used by the endpoint to determine HTTP response codes
class IngestError(Exception):
    pass

class NotFoundError(IngestError):
    pass

class DownloadTimeout(IngestError):
    pass

class TooLargeError(IngestError):
    pass

# Caps (hackathon-friendly defaults)
MAX_TOTAL_UNCOMPRESSED = 25 * 1024 * 1024  # 25 MB
MAX_FILES_EXTRACT = 2000
MAX_SINGLE_FILE_SIZE = 500 * 1024  # 500 KB
MAX_FILES_IN_MEMORY = 400
MAX_CHARS_PER_FILE = 200_000

# filters
SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "venv", "__pycache__"}
ALLOWED_EXT = {
    ".js", ".ts", ".py", ".java", ".go", ".rb", ".php", ".cs", ".c", ".cpp",
    ".json", ".yml", ".yaml", ".toml", ".env", ".sh", ".html", ".css"
}

CODELOAD_URL = "https://codeload.github.com/{owner}/{repo}/zip/{ref}"

async def ingest_repo(owner: str, repo: str, ref: str = "main", subpath: Optional[str] = None, *, timeout: int = 30) -> Tuple[FilesPayload, Stats]:
    """Download the GitHub archive for owner/repo@ref, inspect and select files to include.

    Returns (FilesPayload, Stats).

    Raises NotFoundError when the codeload returns 404.
    Raises DownloadTimeout on timeout.
    Raises TooLargeError when caps exceeded.
    Raises IngestError for other failures.
    """
    url = CODELOAD_URL.format(owner=owner, repo=repo, ref=ref)

    stats = Stats()
    files: List[SourceFile] = []
    metadata = FilesMetadata()

    # Download archive to temp file (streamed)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
    except httpx.ReadTimeout as e:
        raise DownloadTimeout("Download timed out") from e
    except Exception as e:
        raise IngestError(f"Download failed: {e}") from e

    if resp.status_code == 404:
        raise NotFoundError("Repository or ref not found on GitHub")
    if resp.status_code >= 400:
        raise IngestError(f"Download failed with HTTP {resp.status_code}")

    # save to temp file
    tmp_zip = None
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp_zip = tmp.name
        tmp.write(resp.content)
        tmp.flush()
        tmp.close()

        # Open the zip and iterate entries
        with zipfile.ZipFile(tmp_zip, 'r') as z:
            entries = z.infolist()
            stats.files_considered = len(entries)

            total_uncompressed = 0
            extracted_count = 0
            included_count = 0
            read_count = 0
            skipped_count = 0

            for info in entries:
                # safety: ignore directories
                name = info.filename
                if name.endswith('/'):
                    skipped_count += 1
                    continue

                # Normalize path: strip top-level folder that GitHub adds (owner-repo-ref/)
                # Many GitHub archives contain a single top-level directory; remove it.
                parts = name.split('/')
                if len(parts) <= 1:
                    rel_path = parts[-1]
                else:
                    rel_path = '/'.join(parts[1:])

                # If a subpath is specified, ensure file is under it
                if subpath:
                    # normalize both
                    if not rel_path.startswith(subpath.rstrip('/') + '/') and rel_path != subpath.rstrip('/'):
                        skipped_count += 1
                        continue
                    # strip subpath prefix
                    rel_path = rel_path[len(subpath.rstrip('/'))+1:] if rel_path.startswith(subpath.rstrip('/') + '/') else ''

                # Skip unwanted directories
                path_parts = rel_path.split('/')
                if any(p in SKIP_DIRS for p in path_parts):
                    skipped_count += 1
                    continue

                # enforce max entries
                extracted_count += 1
                if extracted_count > MAX_FILES_EXTRACT:
                    metadata.truncated = True
                    metadata.reason = 'max_files_extracted_reached'
                    stats.truncated = True
                    stats.reason = metadata.reason
                    break

                # check uncompressed sizes via ZipInfo.file_size
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_TOTAL_UNCOMPRESSED:
                    metadata.truncated = True
                    metadata.reason = 'max_total_uncompressed_reached'
                    stats.truncated = True
                    stats.reason = metadata.reason
                    break

                stats.total_uncompressed_bytes = total_uncompressed

                # extension filter
                _, ext = os.path.splitext(rel_path.lower())
                if ext not in ALLOWED_EXT:
                    skipped_count += 1
                    continue

                # skip too large single files
                if info.file_size > MAX_SINGLE_FILE_SIZE:
                    skipped_count += 1
                    continue

                # We will consider this file
                included_count += 1
                stats.files_included = included_count

                # Read into memory only up to MAX_FILES_IN_MEMORY
                if read_count >= MAX_FILES_IN_MEMORY:
                    # do not read more into memory; mark truncated and stop collecting
                    metadata.truncated = True
                    metadata.reason = 'max_files_in_memory_reached'
                    stats.truncated = True
                    stats.reason = metadata.reason
                    break

                try:
                    with z.open(info, 'r') as fh:
                        # Read up to MAX_CHARS_PER_FILE bytes
                        raw = fh.read(MAX_CHARS_PER_FILE + 1)
                        if isinstance(raw, bytes):
                            try:
                                text = raw.decode('utf-8')
                            except UnicodeDecodeError:
                                # try latin-1 fallback
                                text = raw.decode('latin-1', errors='replace')
                        else:
                            text = str(raw)

                        # If we read more than the cap, mark truncated
                        if len(text) > MAX_CHARS_PER_FILE:
                            text = text[:MAX_CHARS_PER_FILE]
                            metadata.truncated = True
                            metadata.reason = 'max_chars_per_file_reached'
                            stats.truncated = True
                            stats.reason = metadata.reason

                        files.append(SourceFile(path=rel_path, content=text))
                        read_count += 1
                        stats.files_read = read_count

                except zipfile.BadZipFile:
                    skipped_count += 1
                    continue
                except Exception:
                    skipped_count += 1
                    continue

            # end for

            stats.files_skipped = skipped_count
            stats.files_considered = len(entries)
            stats.files_included = included_count

    finally:
        # cleanup temp zip
        try:
            if tmp_zip and os.path.exists(tmp_zip):
                os.unlink(tmp_zip)
        except Exception:
            pass

    repo_meta = InputRepository(owner=owner, name=repo, ref=ref, subpath=subpath)
    payload = FilesPayload(repo=repo_meta, files=files, metadata=metadata)

    return payload, stats
