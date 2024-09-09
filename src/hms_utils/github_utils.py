import os
import requests
from typing import Optional


def get_github_commit_date(repo: str, commit: str, github_token: Optional[str] = None,
                           raise_exception: bool = False) -> Optional[str]:
    try:
        request = f"{repo}/commits/{commit}"
        if (response := _get_github_info(request, github_token=github_token, raise_exception=raise_exception)):
            return response.get("commit", {}).get("author", {}).get("date")
    except Exception as e:
        if raise_exception is True:
            raise e
    return None


def get_github_latest_commit(repo: str, branch: str, github_token: Optional[str] = None,
                             raise_exception: bool = False) -> Optional[str]:
    try:
        request = f"{repo}/branches/{branch}"
        if (response := _get_github_info(request, github_token=github_token, raise_exception=raise_exception)):
            return response.get("commit", {}).get("sha")
    except Exception as e:
        if raise_exception is True:
            raise e
    return None


def _get_github_info(request: str, github_token: Optional[str] = None, raise_exception: bool = False) -> Optional[dict]:
    url = f"https://api.github.com/repos/{request}"
    if (not github_token) and (not (github_token := os.environ.get("GITHUB_TOKEN"))):
        return None
    try:
        headers = {"Authorization": f"token {github_token}"}
        if (response := requests.get(url, headers=headers)).status_code == 200:
            return response.json()
    except Exception as e:
        if raise_exception is True:
            raise e
    return None
