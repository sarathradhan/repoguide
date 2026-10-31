"""Service for interacting with GitHub REST API and raw file content retrieval."""
import asyncio
import logging
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.models.repository import RepositoryFile, RepositoryResponse
from app.services.code_parser import CodeParser

logger = logging.getLogger("repoguide.github")

# GitHub API endpoints
GITHUB_API_BASE = "https://api.github.com"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"


class GitHubService:
    """Handles parsing, metadata fetching, tree traversal, and content downloading from GitHub."""

    @classmethod
    def parse_repo_url(cls, url: str) -> Tuple[str, str]:
        """
        Parse and validate a GitHub repository URL into (owner, repo).

        Examples accepted:
        - https://github.com/psf/requests
        - https://github.com/psf/requests.git
        - https://github.com/psf/requests/
        - github.com/psf/requests
        """
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        pattern = r"^https?://(?:www\.)?github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?(?:/.*)?$"
        match = re.match(pattern, url, re.IGNORECASE)
        if not match:
            raise ValueError(
                f"Invalid GitHub repository URL: '{url}'. Expected format: https://github.com/owner/repository"
            )

        owner = match.group(1).strip()
        repo = match.group(2).strip()

        # Disallow unsafe names
        if owner in [".", ".."] or repo in [".", ".."]:
            raise ValueError("Repository owner or name is invalid.")

        return owner, repo

    @classmethod
    def _get_api_headers(cls) -> Dict[str, str]:
        """Generate HTTP headers for GitHub REST API calls."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"RepoGuide-AI/{settings.APP_VERSION}",
        }
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"
        return headers

    @classmethod
    async def fetch_repo_metadata(
        cls, client: httpx.AsyncClient, owner: str, repo: str
    ) -> Dict:
        """Fetch repository metadata from GitHub REST API."""
        url = f"{GITHUB_API_BASE}/repos/{quote(owner)}/{quote(repo)}"
        try:
            response = await client.get(url, headers=cls._get_api_headers(), timeout=15.0)
        except httpx.TimeoutException:
            logger.error("Timeout fetching repository metadata for %s/%s", owner, repo)
            raise HTTPException(
                status_code=504,
                detail=f"Connection to GitHub timed out while fetching repository metadata for {owner}/{repo}.",
            )
        except httpx.RequestError as exc:
            logger.error("Network error fetching metadata for %s/%s: %s", owner, repo, exc)
            raise HTTPException(
                status_code=502,
                detail=f"Network error communicating with GitHub: {str(exc)}",
            )

        if response.status_code == 200:
            return response.json()

        # Handle rate limits
        if response.status_code == 403:
            rate_remaining = response.headers.get("x-ratelimit-remaining", "")
            if rate_remaining == "0" or "rate limit" in response.text.lower():
                logger.warning("GitHub API rate limit exceeded")
                raise HTTPException(
                    status_code=429,
                    detail=(
                        "GitHub API rate limit reached. "
                        "Please configure a GITHUB_TOKEN in backend/.env to increase quota, or try again later."
                    ),
                )
            raise HTTPException(
                status_code=403,
                detail="Access forbidden by GitHub API. Please check your credentials or permissions.",
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Repository '{owner}/{repo}' not found on GitHub. Make sure it is public and spelled correctly.",
            )

        raise HTTPException(
            status_code=response.status_code,
            detail=f"GitHub API returned error {response.status_code}: {response.text[:200]}",
        )

    @classmethod
    async def fetch_tree(
        cls, client: httpx.AsyncClient, owner: str, repo: str, branch: str
    ) -> List[Dict]:
        """Fetch the full recursive Git tree for the given branch."""
        url = f"{GITHUB_API_BASE}/repos/{quote(owner)}/{quote(repo)}/git/trees/{quote(branch)}?recursive=1"
        try:
            response = await client.get(url, headers=cls._get_api_headers(), timeout=20.0)
        except httpx.TimeoutException:
            logger.error("Timeout fetching repository tree for %s/%s @ %s", owner, repo, branch)
            raise HTTPException(
                status_code=504,
                detail="Connection to GitHub timed out while fetching repository file tree.",
            )
        except httpx.RequestError as exc:
            logger.error("Network error fetching tree for %s/%s: %s", owner, repo, exc)
            raise HTTPException(
                status_code=502,
                detail=f"Network error retrieving repository tree from GitHub: {str(exc)}",
            )

        if response.status_code == 200:
            tree_data = response.json()
            return tree_data.get("tree", [])

        if response.status_code == 403:
            raise HTTPException(
                status_code=429,
                detail="GitHub API rate limit exceeded while retrieving repository tree.",
            )

        if response.status_code == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Git tree not found for branch '{branch}'. The repository might be empty.",
            )

        raise HTTPException(
            status_code=response.status_code,
            detail=f"Failed to fetch file tree from GitHub: {response.text[:200]}",
        )

    @classmethod
    async def _download_single_file(
        cls,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        owner: str,
        repo: str,
        branch: str,
        file_path: str,
    ) -> Optional[RepositoryFile]:
        """Download and decode a single source file safely using a concurrency semaphore."""
        # Clean path parts to prevent SSRF / directory traversal
        sanitized_path = "/".join(part for part in file_path.split("/") if part not in [".", ".."])
        raw_url = f"{GITHUB_RAW_BASE}/{quote(owner)}/{quote(repo)}/{quote(branch)}/{sanitized_path}"

        headers = {
            "User-Agent": f"RepoGuide-AI/{settings.APP_VERSION}",
        }
        if settings.GITHUB_TOKEN:
            headers["Authorization"] = f"token {settings.GITHUB_TOKEN}"

        async with semaphore:
            try:
                response = await client.get(raw_url, headers=headers, timeout=12.0)
                if response.status_code == 200:
                    # Enforce per-file size check on downloaded content
                    content_bytes = response.content
                    size = len(content_bytes)

                    if size > settings.MAX_FILE_SIZE_BYTES:
                        logger.info("Skipping %s: size %d exceeds %d limit", file_path, size, settings.MAX_FILE_SIZE_BYTES)
                        return None

                    # Decode content as UTF-8 text with replace on decode errors
                    content_text = content_bytes.decode("utf-8", errors="replace")
                    language = CodeParser.get_language(file_path) or "Text"

                    return RepositoryFile(
                        path=file_path,
                        language=language,
                        content=content_text,
                        size=size,
                    )

                logger.warning(
                    "Non-200 (%s) downloading %s from raw GitHub",
                    response.status_code,
                    file_path,
                )
                return None
            except Exception as exc:
                logger.warning("Error downloading file %s: %s", file_path, exc)
                return None

    @classmethod
    async def ingest_repository(cls, repo_url: str) -> RepositoryResponse:
        """
        Orchestrate complete repository ingestion:
        1. Parse URL
        2. Fetch repo metadata
        3. Fetch git tree
        4. Filter source files
        5. Download file contents concurrently
        6. Apply limits and return structured RepositoryResponse
        """
        owner, repo = cls.parse_repo_url(repo_url)

        async with httpx.AsyncClient() as client:
            # 1. Fetch Metadata
            meta = await cls.fetch_repo_metadata(client, owner, repo)
            default_branch = meta.get("default_branch", "main")
            description = meta.get("description")
            stars = meta.get("stargazers_count", 0)

            # 2. Fetch Recursive Tree
            tree_items = await cls.fetch_tree(client, owner, repo, default_branch)

            if not tree_items:
                return RepositoryResponse(
                    owner=owner,
                    repository=repo,
                    description=description,
                    default_branch=default_branch,
                    stars=stars,
                    total_source_files_found=0,
                    files_returned=0,
                    files_truncated=False,
                    truncation_reason="Repository appears to be empty.",
                    files=[],
                )

            # 3. Filter Source Files and Apply Count Limit
            selected_items, total_found, is_truncated, truncation_reason = CodeParser.filter_tree(
                tree_items
            )

            # 4. Concurrently download files with semaphore
            semaphore = asyncio.Semaphore(settings.CONCURRENT_DOWNLOADS_LIMIT)
            download_tasks = [
                cls._download_single_file(
                    client=client,
                    semaphore=semaphore,
                    owner=owner,
                    repo=repo,
                    branch=default_branch,
                    file_path=item["path"],
                )
                for item in selected_items
            ]

            results = await asyncio.gather(*download_tasks, return_exceptions=False)

            # 5. Enforce total content size limit (MAX_TOTAL_SIZE_BYTES)
            valid_files: List[RepositoryFile] = []
            total_bytes = 0
            size_limit_hit = False

            for f in results:
                if f is not None:
                    if total_bytes + f.size > settings.MAX_TOTAL_SIZE_BYTES:
                        size_limit_hit = True
                        break
                    valid_files.append(f)
                    total_bytes += f.size

            if size_limit_hit:
                is_truncated = True
                max_mb = settings.MAX_TOTAL_SIZE_BYTES // (1024 * 1024)
                truncation_reason = (
                    f"Total source code size exceeded {max_mb} MB limit. "
                    f"Truncated to {len(valid_files)} files."
                )

            return RepositoryResponse(
                owner=owner,
                repository=repo,
                description=description,
                default_branch=default_branch,
                stars=stars,
                total_source_files_found=total_found,
                files_returned=len(valid_files),
                files_truncated=is_truncated,
                truncation_reason=truncation_reason,
                files=valid_files,
            )

