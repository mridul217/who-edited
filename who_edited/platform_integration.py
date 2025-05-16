import requests
import json
import os
import urllib.parse
from typing import Dict, List, Optional, Union, Any
from pathlib import Path
from datetime import datetime
import webbrowser

from who_edited.git_tools import run_git_command


class GitHubAPI:
    """Class for interacting with GitHub API."""
    
    def __init__(self, token: Optional[str] = None):
        """Initialize with optional token."""
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
            
    def get_repo_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information."""
        url = f"{self.base_url}/repos/{owner}/{repo}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
        
    def get_pull_requests(self, owner: str, repo: str, state: str = "all") -> List[Dict[str, Any]]:
        """Get repository pull requests."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {"state": state}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
        
    def get_pr_for_commit(self, owner: str, repo: str, commit_hash: str) -> Optional[Dict[str, Any]]:
        """Find the pull request associated with a commit."""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_hash}/pulls"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        prs = response.json()
        return prs[0] if prs else None
        
    def get_reviews_for_pr(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Get reviews for a pull request."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
        
    def get_review_comments(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """Get review comments for a pull request."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()


class GitLabAPI:
    """Class for interacting with GitLab API."""
    
    def __init__(self, token: Optional[str] = None, base_url: str = "https://gitlab.com/api/v4"):
        """Initialize with optional token and base URL."""
        self.token = token or os.environ.get("GITLAB_TOKEN")
        self.base_url = base_url
        self.headers = {}
        if self.token:
            self.headers["PRIVATE-TOKEN"] = self.token
            
    def get_repo_info(self, project_id: Union[str, int]) -> Dict[str, Any]:
        """Get repository information."""
        url = f"{self.base_url}/projects/{urllib.parse.quote_plus(str(project_id))}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
        
    def get_merge_requests(self, project_id: Union[str, int], state: str = "all") -> List[Dict[str, Any]]:
        """Get project merge requests."""
        url = f"{self.base_url}/projects/{urllib.parse.quote_plus(str(project_id))}/merge_requests"
        params = {"state": state}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()
        
    def get_mr_for_commit(self, project_id: Union[str, int], commit_hash: str) -> Optional[Dict[str, Any]]:
        """Find the merge request associated with a commit."""
        url = f"{self.base_url}/projects/{urllib.parse.quote_plus(str(project_id))}/repository/commits/{commit_hash}/merge_requests"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        mrs = response.json()
        return mrs[0] if mrs else None
        
    def get_merge_request_discussions(self, project_id: Union[str, int], mr_iid: int) -> List[Dict[str, Any]]:
        """Get discussions (comments) for a merge request."""
        url = f"{self.base_url}/projects/{urllib.parse.quote_plus(str(project_id))}/merge_requests/{mr_iid}/discussions"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()


def parse_git_remote_url(remote_url: str) -> Dict[str, str]:
    """
    Parse a git remote URL to extract platform, owner, and repo.
    
    Args:
        remote_url: Git remote URL
        
    Returns:
        Dictionary with platform, owner, and repo
    """
    result = {
        "platform": None,
        "owner": None,
        "repo": None
    }
    
    # Clean up the URL
    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]
        
    # Handle SSH URLs (git@github.com:owner/repo.git)
    if remote_url.startswith("git@"):
        parts = remote_url.split(":")
        if len(parts) == 2:
            host = parts[0].split("@")[1]
            repo_path = parts[1]
            
            if "github.com" in host:
                result["platform"] = "github"
            elif "gitlab" in host:
                result["platform"] = "gitlab"
                
            path_parts = repo_path.split("/")
            if len(path_parts) >= 2:
                result["owner"] = path_parts[0]
                result["repo"] = "/".join(path_parts[1:])
    
    # Handle HTTPS URLs (https://github.com/owner/repo)
    elif remote_url.startswith(("http://", "https://")):
        parts = remote_url.split("/")
        
        if "github.com" in remote_url:
            result["platform"] = "github"
            if len(parts) >= 5:
                result["owner"] = parts[3]
                result["repo"] = "/".join(parts[4:])
                
        elif "gitlab" in remote_url:
            result["platform"] = "gitlab"
            if len(parts) >= 5:
                result["owner"] = parts[3]
                result["repo"] = "/".join(parts[4:])
                
    return result


def get_pr_for_file_line(file_path: str, line_number: int) -> Optional[Dict[str, Any]]:
    """
    Get the pull request that introduced a specific line.
    
    Args:
        file_path: Path to the file
        line_number: Line number
        
    Returns:
        Pull request information or None
    """
    try:
        file_path = Path(file_path).resolve()
        repo_dir = file_path.parent
        
        # Get commit hash for the line
        blame_output = run_git_command(
            ["git", "blame", f"-L{line_number},{line_number}", file_path.name],
            cwd=repo_dir
        )
        commit_hash = blame_output.split()[0]
        
        # Get repository remote URL
        remote_url = run_git_command(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repo_dir
        )
        
        # Parse the remote URL to get platform, owner, and repo
        remote_info = parse_git_remote_url(remote_url)
        
        if not all([remote_info["platform"], remote_info["owner"], remote_info["repo"]]):
            return None
            
        # Get PR/MR information based on platform
        if remote_info["platform"] == "github":
            github_api = GitHubAPI()
            return github_api.get_pr_for_commit(
                remote_info["owner"],
                remote_info["repo"],
                commit_hash
            )
        elif remote_info["platform"] == "gitlab":
            gitlab_api = GitLabAPI()
            project_path = f"{remote_info['owner']}/{remote_info['repo']}"
            return gitlab_api.get_mr_for_commit(project_path, commit_hash)
            
        return None
        
    except Exception as e:
        print(f"Error getting PR for file line: {e}")
        return None


def get_review_comments_for_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Get review comments for a file across all PRs.
    
    Args:
        file_path: Path to the file
        
    Returns:
        List of review comments
    """
    try:
        file_path = Path(file_path).resolve()
        repo_dir = file_path.parent
        
        # Get repository remote URL
        remote_url = run_git_command(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=repo_dir
        )
        
        # Parse the remote URL to get platform, owner, and repo
        remote_info = parse_git_remote_url(remote_url)
        
        if not all([remote_info["platform"], remote_info["owner"], remote_info["repo"]]):
            return []
            
        # Get relative file path
        repo_root = run_git_command(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=repo_dir
        )
        relative_path = str(file_path.relative_to(repo_root))
        
        all_comments = []
        
        # Get PR/MR comments based on platform
        if remote_info["platform"] == "github":
            github_api = GitHubAPI()
            prs = github_api.get_pull_requests(remote_info["owner"], remote_info["repo"], state="all")
            
            for pr in prs:
                comments = github_api.get_review_comments(
                    remote_info["owner"],
                    remote_info["repo"],
                    pr["number"]
                )
                
                # Filter comments for this file
                file_comments = [
                    {
                        "body": c["body"],
                        "author": c["user"]["login"],
                        "line": c.get("line", c.get("original_line")),
                        "date": c["created_at"],
                        "pr_number": pr["number"],
                        "pr_title": pr["title"],
                        "url": c["html_url"]
                    }
                    for c in comments
                    if c.get("path") == relative_path
                ]
                
                all_comments.extend(file_comments)
                
        elif remote_info["platform"] == "gitlab":
            gitlab_api = GitLabAPI()
            project_path = f"{remote_info['owner']}/{remote_info['repo']}"
            mrs = gitlab_api.get_merge_requests(project_path, state="all")
            
            for mr in mrs:
                discussions = gitlab_api.get_merge_request_discussions(project_path, mr["iid"])
                
                for discussion in discussions:
                    for note in discussion.get("notes", []):
                        if note.get("type") == "DiffNote" and note.get("position", {}).get("new_path") == relative_path:
                            all_comments.append({
                                "body": note["body"],
                                "author": note["author"]["username"],
                                "line": note["position"].get("new_line"),
                                "date": note["created_at"],
                                "mr_number": mr["iid"],
                                "mr_title": mr["title"],
                                "url": note["url"]
                            })
        
        return all_comments
        
    except Exception as e:
        print(f"Error getting review comments: {e}")
        return []


def open_pr_page_for_line(file_path: str, line_number: int) -> bool:
    """
    Open the PR page that introduced a specific line.
    
    Args:
        file_path: Path to the file
        line_number: Line number
        
    Returns:
        True if successful, False otherwise
    """
    try:
        pr_info = get_pr_for_file_line(file_path, line_number)
        if pr_info and pr_info.get("html_url"):
            webbrowser.open(pr_info["html_url"])
            return True
        return False
        
    except Exception as e:
        print(f"Error opening PR page: {e}")
        return False 