import argparse
import logging
import os
import sys
from typing import Dict, Optional

import requests


class InfoFilter(logging.Filter):
    def filter(self, record):
        return record.levelno == logging.INFO


# Only route info logs to stdout, the rest goes to stderr
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

info_handler = logging.StreamHandler(sys.stdout)
info_handler.setLevel(logging.INFO)
info_handler.addFilter(InfoFilter())
info_format = logging.Formatter("%(message)s")
info_handler.setFormatter(info_format)

other_handler = logging.StreamHandler(sys.stderr)
other_handler.setLevel(logging.DEBUG)
other_format = logging.Formatter("%(levelname)s - %(message)s")
other_handler.setFormatter(other_format)

LOGGER.addHandler(info_handler)
LOGGER.addHandler(other_handler)


class Github:
    def __init__(self, token: str, repo: str) -> None:
        if None in (token, repo):
            raise ValueError(
                "Please provide a token and repo. See --help for more info."
            )
        self._headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self._REPO = repo

    def create_release(
        self,
        release_tag,
        title,
        body,
        draft=False,
        prerelease=False,
        make_latest="false",
    ):
        url = f"https://api.github.com/repos/{self._REPO}/releases"
        data = {
            "tag_name": release_tag,
            "draft": draft,
            "prerelease": prerelease,
            "make_latest": make_latest,
            "name": title,
            "body": body,
        }
        response = requests.post(url, json=data, headers=self._headers)
        if response.status_code == 201:
            LOGGER.debug(f"Release created for tag: {release_tag}")
        else:
            LOGGER.error(
                f"Failed to create release for {release_tag}: {response.content}"
            )
        return response.json()

    def update_release(
        self,
        *,
        release_id,
        tag_name=None,
        title=None,
        body=None,
        draft=None,
        prerelease=None,
        make_latest=None,
    ):
        url = f"https://api.github.com/repos/{self._REPO}/releases/{release_id}"
        data = {
            "release_id": release_id,
        }
        if title:
            data["name"] = title
        if tag_name:
            data["tag_name"] = tag_name
        if body:
            data["body"] = body
        if draft:
            data["draft"] = draft
        if prerelease:
            data["prerelease"] = prerelease
        if make_latest:
            data["make_latest"] = make_latest

        response = requests.patch(url, json=data, headers=self._headers)
        if response.status_code == 200:
            LOGGER.debug(f"Release updated for id: {release_id}")
        else:
            LOGGER.error(
                f"Failed to update release for {release_id}: {response.json()}"
            )
        return response.json()

    def generate_release_notes(
        self, release_tag: str, previous_tag: Optional[str]
    ) -> Optional[Dict]:
        url = f"https://api.github.com/repos/{self._REPO}/releases/generate-notes"
        data = {
            "tag_name": release_tag,
        }
        if previous_tag:
            data["previous_tag_name"] = previous_tag
        response = requests.post(url, json=data, headers=self._headers)
        if response.status_code != 200:
            LOGGER.error(f"Failed to generate release notes for {release_tag}")
            return None
        payload = response.json()
        return {"title": payload["name"], "body": payload["body"]}

    def check_release_exists(self, tag_name):
        url = f"https://api.github.com/repos/{self._REPO}/releases/tags/{tag_name}"
        response = requests.get(url, headers=self._headers)
        return response.status_code == 200

    def get_release_by_tag(self, tag_name) -> Optional[Dict]:
        url = f"https://api.github.com/repos/{self._REPO}/releases/tags/{tag_name}"
        response = requests.get(url, headers=self._headers)
        # Tag may not exist yet
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            LOGGER.error(
                f"Unexpected response {response.status_code} {response.content}"
            )
            return None
        return response.json()

    def get_latest_release_tag(self) -> Optional[str]:
        url = f"https://api.github.com/repos/{self._REPO}/releases/latest"
        response = requests.get(url, headers=self._headers)
        # There might not be a latest release yet
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise RuntimeError("Something went wrong fetching the latest release")
        return response.json()["tag_name"]

    def get_default_branch(self) -> str:
        url = f"https://api.github.com/repos/{self._REPO}"
        response = requests.get(url, headers=self._headers)
        response.raise_for_status()
        data = response.json()
        return data.get("default_branch")


class NewRelease:
    def __init__(self, github: Github) -> None:
        self.github = github

    def create(self, new_tag: str):
        previous_release_tag = self.github.get_latest_release_tag()
        release_notes = self.github.generate_release_notes(
            new_tag, previous_release_tag
        )
        if not release_notes:
            raise RuntimeError("Invalid release notes")
        return self.github.create_release(
            new_tag,
            release_notes["title"],
            release_notes["body"],
            draft=False,
            make_latest="true",
        )


def extract_release_link_from_response(response: Optional[dict]) -> Optional[str]:
    if not response:
        return None
    return response.get("html_url")


class ReleaseCandidate:
    TAG = "release-candidate"

    def __init__(self, github: Github) -> None:
        self.github = github
        self.release_id = self.get_or_create_release_candidate()["id"]

    def get_or_create_release_candidate(self) -> Dict:
        release = self.github.get_release_by_tag(self.TAG)
        return release or self.create_release_candidate()

    def create_release_candidate(self) -> Dict:
        return self.github.create_release(
            release_tag=self.TAG,
            title="Release Candidate",
            body="Exciting things to come...",
            draft=False,
            prerelease=True,
            make_latest="false",
        )

    def update_release_candidate(self) -> dict:
        latest_release = self.github.get_latest_release_tag()
        release_notes = self.github.generate_release_notes(
            "release-candidate", latest_release
        )
        if not release_notes:
            raise RuntimeError("Release notes did not generate")
        return self.github.update_release(
            release_id=self.release_id,
            title="Release Candidate",
            body=release_notes["body"],
            draft=False,
            prerelease=True,
            make_latest="false",
        )

    def empty(self) -> dict:
        return self.github.update_release(
            release_id=self.release_id,
            title="Release Candidate",
            body="Nothing here at the moment...",
        )


def main():
    parser = argparse.ArgumentParser(description="Release management script")

    parser.add_argument(
        "--github-token",
        type=str,
        help="GitHub token for authentication",
        default=os.getenv("GITHUB_TOKEN"),
    )
    parser.add_argument(
        "--repo",
        type=str,
        help="Repository with owner and name. Eg bob/my-repo",
        default=os.getenv("REPO"),
    )

    # Main command
    subparsers = parser.add_subparsers(dest="command")
    # Subcommand: default-branch
    parser_default_branch = subparsers.add_parser(
        "default-branch", help="Retrieve the current default branch of the repository"
    )

    # Subcommand: candidate
    parser_candidate = subparsers.add_parser(
        "candidate", help="Manage release candidate"
    )
    candidate_subparsers = parser_candidate.add_subparsers(dest="candidate_command")

    # Subcommand: candidate update
    parser_candidate_update = candidate_subparsers.add_parser(
        "update", help="Update release candidate"
    )

    # Subcommand: candidate clear
    parser_candidate_clear = candidate_subparsers.add_parser(
        "clear", help="Clear release candidate"
    )

    # Subcommand: release
    parser_release = subparsers.add_parser("release", help="Create a new release")
    parser_release.add_argument("tag_name", type=str, help="Tag name for the release")

    # Parse arguments
    args = parser.parse_args()

    github = Github(token=args.github_token, repo=args.repo)
    if args.command == "default-branch":
        return github.get_default_branch()

    if args.command == "candidate":
        candidate_handler = ReleaseCandidate(github)
        if args.candidate_command == "update":
            return extract_release_link_from_response(
                candidate_handler.update_release_candidate()
            )
        if args.candidate_command == "clear":
            return extract_release_link_from_response(candidate_handler.empty())

    if args.command == "release":
        return extract_release_link_from_response(NewRelease(github).create(args.tag_name))

    return parser.print_help()


if __name__ == "__main__":
    LOGGER.info(main())
