"""GitHub API client for Loom."""

import base64

import httpx


class GitHubClient:
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "loom-agent",
        }

    async def get_pr_comments(self, pr_num: int) -> list[str]:
        """Fetch all review + issue comments on a PR."""
        comments = []
        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            # Inline review comments
            rc = await client.get(
                f"https://api.github.com/repos/{self.repo}/pulls/{pr_num}/comments"
            )
            if rc.status_code == 200:
                comments.extend(c["body"] for c in rc.json())

            # Issue comments
            ic = await client.get(
                f"https://api.github.com/repos/{self.repo}/issues/{pr_num}/comments"
            )
            if ic.status_code == 200:
                comments.extend(c["body"] for c in ic.json())
        return comments

    async def get_pr_diff(self, pr_num: int) -> str:
        """Fetch the raw diff of a PR."""
        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{self.repo}/pulls/{pr_num}",
                headers={**self._headers, "Accept": "application/vnd.github.diff"},
            )
            resp.raise_for_status()
            return resp.text

    async def read_file(self, path: str) -> tuple[str, str]:
        """Read a file from the repo. Returns (content, sha)."""
        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{self.repo}/contents/{path}"
            )
            if resp.status_code == 404:
                return "", ""
            resp.raise_for_status()
            data = resp.json()
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content, data["sha"]

    async def write_file(
        self, path: str, content: str, sha: str, message: str
    ) -> bool:
        """Create or update a file in the repo. Returns True on success."""
        body = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
        }
        if sha:
            body["sha"] = sha

        async with httpx.AsyncClient(headers=self._headers, timeout=15) as client:
            resp = await client.put(
                f"https://api.github.com/repos/{self.repo}/contents/{path}",
                json=body,
            )
            return resp.status_code in (200, 201)
