from __future__ import annotations
from boto3 import client as BotoClient
from functools import lru_cache
import re
import time
from typing import Dict, Generator, List, Optional, Tuple
from dcicutils.datetime_utils import format_datetime
from hms_utils.github_utils import get_github_commit_date, get_github_latest_commit


def get_aws_ecr_build_info(image_repo_or_arn: str, image_tag: str,
                           image_digest: str, previous_builds: int = 8) -> Optional[dict]:
    """
    Returns a dictionary with info about the three most recent CodeBuild builds
    for the given image repo and tag, or None if none found.
    """
    if not image_tag:
        image_repo, image_tag = _get_image_repo_and_tag(image_repo_or_arn)
    else:
        image_repo = image_repo_or_arn

    codebuild = BotoClient("codebuild")

    def get_projects() -> List[str]:

        projects = codebuild.list_projects()["projects"]

        # If there is a project with the same name as the image_repo then look at that one first,
        # or secondarily, prefer projects whose names contain the image_repo and/or image_tag;
        # we do this just for performance, to try to reduce the number of boto calls we make.

        def prefer_project(preferred_project: str):
            projects.remove(preferred_project)
            return [preferred_project, *projects]

        projects = [project for project in projects
                    if "pipeline" not in project.lower() and "tibanna" not in project.lower()]

        preferred_project = [project for project in projects if project == image_repo]
        if preferred_project:
            return prefer_project(preferred_project[0])
        preferred_project = [project for project in projects
                             if image_repo.lower() in project.lower() and image_tag.lower() in project.lower()]
        if preferred_project:
            return prefer_project(preferred_project[0])
        preferred_project = [project for project in projects if image_repo.lower() in project.lower()]
        if preferred_project:
            return prefer_project(preferred_project[0])
        preferred_project = [project for project in projects if image_tag.lower() in project.lower()]
        if preferred_project:
            return prefer_project(preferred_project[0])
        return projects

    def get_relevant_builds(project: str) -> Generator[Optional[Dict], None, None]:

        # For efficiency, and the most common actual case, get builds three at a time; i.e. since we
        # want to the three most recent (relevant) builds, and they are usually together at the start
        # of the (list_build_for_projects) list ordered (descending) by build (creation) time;
        # but of course, just in case, we need to handle the general case.

        def get_relevant_build_info(build: Optional[Dict]) -> Optional[Dict]:

            def create_build_info(build: Dict) -> Dict:
                return {
                    # "arn": _shortened_arn(build["arn"]),
                    "arn": build["arn"],
                    "project": project,
                    "image_repo": image_repo,
                    "image_tag": image_tag,
                    "github": build.get("source", {}).get("location"),
                    "branch": build.get("sourceVersion"),
                    "commit": build.get("resolvedSourceVersion"),
                    "number": build.get("buildNumber"),
                    # "initiator": _shortened_arn(build.get("initiator")),
                    "initiator": build.get("initiator"),
                    "status": build.get("buildStatus"),
                    "success": is_build_success(build),
                    "finished": build.get("buildComplete"),
                    "started_at": format_datetime(build.get("startTime")),
                    "finished_at": format_datetime(build.get("endTime")),
                    "log_group": build.get("logs", {}).get("groupName"),
                    "log_stream": build.get("logs", {}).get("streamName")
                }

            def is_build_success(build: Dict) -> bool:
                return build.get("buildStatus", "").upper() in ["SUCCEEDED", "SUCCESS"]

            def find_environment_variable(environment_variables: List[Dict], name: str) -> Optional[str]:
                value = [item["value"] for item in environment_variables if item["name"] == name]
                return value[0] if len(value) == 1 else None

            if build and is_build_success(build):
                environment_variables = build.get("environment", {}).get("environmentVariables", {})
                build_image_repo = find_environment_variable(environment_variables, "IMAGE_REPO_NAME")
                if build_image_repo:
                    pass  # TODO
                build_image_tag = find_environment_variable(environment_variables, "IMAGE_TAG")
                if build_image_repo == image_repo and build_image_tag == image_tag:
                    return create_build_info(build)
            return None

        get_builds_from_boto_this_many_at_a_time = 4
        nbuilds = 0
        next_token = None
        while True:
            if nbuilds >= previous_builds:
                break
            if next_token:
                build_ids = codebuild.list_builds_for_project(projectName=project, nextToken=next_token)
            else:
                build_ids = codebuild.list_builds_for_project(projectName=project, sortOrder="DESCENDING")
            next_token = build_ids.get("nextToken")
            build_ids = build_ids["ids"]
            while build_ids:
                build_ids_batch = build_ids[:get_builds_from_boto_this_many_at_a_time]
                build_ids = build_ids[get_builds_from_boto_this_many_at_a_time:]
                builds = codebuild.batch_get_builds(ids=build_ids_batch)["builds"]
                for build in builds:
                    if nbuilds >= previous_builds:
                        break
                    nbuilds += 1
                    build = get_relevant_build_info(build)
                    if build:
                        yield build
            if not next_token:
                break

    for project in get_projects():
        for build in get_relevant_builds(project):
            if image_digest:
                if build_image_digest := _get_aws_codebuild_digest(build["log_group"], build["log_stream"], image_tag):
                    if image_digest == build_image_digest:
                        return build
    return None


@lru_cache
def get_build_info(image_repo: str, image_tag: str, image_digest: Optional[str] = None) -> Optional[Dict]:
    # Cache this result within the enclosing function; for the below services loop.
    return get_aws_ecr_build_info(image_repo, image_tag, image_digest)


def get_image_build_info(image_repo: str, image_tag: str, image_digest: str) -> Optional[dict]:
    if build_info := get_build_info(image_repo, image_tag, image_digest):
        if git_repo := build_info.get("github"):
            git_repo = git_repo.replace("https://github.com/", "")
        git_branch = build_info.get("branch")
        git_commit = build_info.get("commit")
        git_commit_date = get_github_commit_date(git_repo, git_commit)
        git_commit_latest = get_github_latest_commit(git_repo, git_branch)
        if git_commit_latest != git_commit:
            git_commit_latest_date = get_github_commit_date(git_repo, git_commit_latest)
        else:
            git_commit_latest_date = git_commit_date
        return {
           "build_project": build_info["project"],
           "repo": git_repo,
           "branch": git_branch,
           "commit": git_commit,
           "commit_date": git_commit_date,
           "commit_latest": git_commit_latest,
           "commit_latest_date": git_commit_latest_date
        }
    return None


def _get_image_repo_and_tag(image_arn: str) -> Tuple[Optional[str], Optional[str]]:
    # image_arn = _shortened_arn(image_arn)
    image_arn = image_arn
    parts = image_arn.split(":")
    return (parts[0], parts[1]) if len(parts) == 2 else (None, None)


def _get_aws_codebuild_digest(log_group: str, log_stream: str, image_tag: Optional[str] = None) -> Optional[str]:
    logs = BotoClient("logs")
    sha256_pattern = re.compile(r"sha256:([0-9a-f]{64})")
    # For some reason this (rarely-ish) intermittently fails with no error;
    # the results just do not contain the digest; don't know why so try a few (4) times.
    for n in range(4):
        if n > 1:
            time.sleep(0.05)
        if not (log_events := logs.get_log_events(logGroupName=log_group,
                                                  logStreamName=log_stream, startFromHead=False)["events"]):
            log_events = logs.get_log_events(logGroupName=log_group,
                                             logStreamName=log_stream, startFromHead=True)["events"]
        for log_event in log_events:
            msg = log_event.get("message")
            # The entrypoint_deployment.bash script at least partially
            # creates this log output, which includes a line like this:
            # green: digest: sha256:c1204f9ff576105d9a56828e2c0645cc6dbcf91abca767ef6fe033a60c483f10 size: 7632
            if msg and "digest:" in msg and "size:" in msg and (not image_tag or f"{image_tag}:" in msg):
                match = sha256_pattern.search(msg)
                if match:
                    return "sha256:" + match.group(1)
    return None
