"""Updat the README file to reflect `contributions.md`.

- Query the GitHub API to get the description and star count for each repository
  listed in `contributions.md`.
- Lay this information out in the README file.
- Format and sort `contributions.md`.

The user does not need to run this script. Just update `contributions.md` and submit
a pull request.

:author: Shay Hill
:created: 2025-07-28
"""

import datetime
import dataclasses
import os
from pathlib import Path
import subprocess

from collections.abc import Iterator
import requests
import re

_CONTRIBUTIONS = Path(__file__).parents[1] / "contributions.md"
_README_HEADER = Path(__file__).parent / "readme_header.md"
_README = Path(__file__).parents[1] / "README.md"
_CONGRATULATIONS = Path(__file__).parent / "congratulations.md"

def _build_readme_table_row_pattern() -> re.Pattern:
    """Build a regex pattern to match the table rows in README.md."""
    sign_col = r"(?P<sign>[+-])"
    url_col = r"\[(?P<anchor>[^\]]+)\]\([^\)]+\)"
    stars_col = r"⭐(?P<stars>\d+)"
    return re.compile(
        r"\s*\|\s*".join([sign_col, url_col, ".*", stars_col]) + r"\s*\|$"
    )

_RE_TR = _build_readme_table_row_pattern()

def _crossed_star_milestone(old_stars: int, new_stars: int) -> bool:
    """Check if the star count crossed a threshold.

    :param old_stars: The old star count.
    :param new_stars: The new star count.
    :return: True if the star count crossed a threshold, False otherwise.
    """
    s_old = str(old_stars)
    s_new = str(new_stars)
    d_old, d_new = map(len, (s_old, s_new))
    if d_old != d_new:
        return True  # crossing a threshold means the digit count changed
    if old_stars == 0:
        return True  # project got its first stars
    if d_old == 1:
        return False  # next congratulation is at 10 stars

    if d_old == 2:
        congrat_every = 25
    elif d_old == 3:
        congrat_every = 100
    else:
        congrat_every = int(float(f"1e{d_old - 1}")) / 4

    return (old_stars // congrat_every) != (new_stars // congrat_every)


def _iter_star_changes() -> Iterator[tuple[str, int, int]]:
    """Yield updated star counts from README.md diff.
    
    :yield: Tuple of (repository name, old star count, new star count).
    """
    result = subprocess.run(
        ["git", "diff", _README],
        capture_output=True,
    )
    file_diff = result.stdout.decode("utf-8", errors="replace")
    diff_rows = filter(None, (_RE_TR.match(x) for x in file_diff.splitlines()))

    sub_anchor: str | None = None
    sub_stars: int = 0
    for row in diff_rows:
        sign, anchor, stars = row.groups()
        if sign == "-":
            sub_anchor = anchor
            sub_stars = int(stars)
        elif sign == "+":
            if anchor != sub_anchor: # an addition, not a replacement
                continue
            yield anchor, sub_stars, int(stars)
        else:
            msg = f"Unexpected sign '{sign}' in diff row: {row}"
            raise ValueError(msg)

def log_star_milestones() -> None:
    """Log star milestones to the console."""
    for anchor, old_stars, new_stars in _iter_star_changes():
        if _crossed_star_milestone(old_stars, new_stars):
            print(
                f"⭐ {anchor} crossed a star threshold: "
                f"{old_stars} -> {new_stars} stars."
            )
            with open(_CONGRATULATIONS, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.datetime.now().isoformat()} - "
                    f"{anchor} crossed a star threshold: "
                    f"{old_stars} -> {new_stars} stars.\n"
                )


def _get_api_url_from_repo_url(repo_url: str) -> str:
    """Format a GitHub repository URL into the API URL.

    :param repo_url: The GitHub repository URL: https://github.com/owner/repo
    :return: The formatted API URL: https://api.github.com/repos/owner/repo
    :raises ValueError: If the URL is not in the expected format.
    """
    try:
        parts = repo_url.rstrip("/").split("/")
        github_index = parts.index("github.com") if "github.com" in parts else -1
        owner = parts[github_index + 1]
        repo = parts[github_index + 2]
    except IndexError as e:
        msg = (
            f"Invalid GitHub URL format."
            + " Expected: 'https://github.com/owner/repo'. Got '{repo_url}'"
        )
        raise ValueError(msg) from e

    return f"https://api.github.com/repos/{owner}/{repo}"


@dataclasses.dataclass
class RepoInfo:
    """Hold description and star count for a GitHub repository."""

    description: str
    stars: int


def _get_repo_info(repo_url: str, token: str) -> RepoInfo:
    """Get repository information from GitHub API.

    :param repo_url: The GitHub repository URL: https://github.com/owner/repo
    :param token: GitHub API token for authentication.
    :return: A dictionary with repository description and star count.
    """
    api_url = _get_api_url_from_repo_url(repo_url)
    api_headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    response = requests.get(api_url, headers=api_headers)
    response.raise_for_status()
    data = response.json()

    return RepoInfo(
        data.get("description") or "*No description provided.*",
        data.get("stargazers_count"),
    )


@dataclasses.dataclass(order=True)
class Contribution:
    """Readme table column information for a contribution."""

    category: str
    url: str
    token: str = dataclasses.field(repr=False, compare=False)

    def __post_init__(self) -> None:
        """Post-initialization processing."""
        self.__repo_info: RepoInfo | None = None

    @property
    def name(self) -> str:
        """Get the name of the contribution."""
        api_url = _get_api_url_from_repo_url(self.url)
        return "/".join(api_url.split("/")[-2:])

    @property
    def _repo_info(self) -> RepoInfo:
        """Get the repository information, caching it."""
        if self.__repo_info is None:
            self.__repo_info = _get_repo_info(self.url, self.token)
        return self.__repo_info

    @property
    def description(self) -> str:
        """Get the description of the repository."""
        return self._repo_info.description

    @property
    def stars(self) -> int:
        """Get the number of stars for the repository."""
        return self._repo_info.stars


def _read_contributions(token: str) -> list[Contribution]:
    """Read d format `contributions.md` into a sorted list.

    :return: (category, url) for each contribution.
    :effect: sorts and formats `contributions.md`
    """
    lines = (x.strip() for x in _CONTRIBUTIONS.read_text().splitlines())
    lines = [x for x in lines if x]
    if not lines[0].startswith("#"):
        msg = f"Expected first line of {_CONTRIBUTIONS} to be a header."
        raise ValueError(msg)
    contributions: set[tuple[str, str]] = set()
    heading = lines[0].lstrip("# ")
    for line in lines[1:]:
        if line.startswith("#"):
            heading = line.lstrip("# ")
        else:
            contributions.add((heading, line))
    return sorted([Contribution(x[0], x[1], token) for x in contributions])


def _overwrite_contributions_md(contributions: list[Contribution]) -> None:
    """Overwrite `contributions.md` with the sorted contributions.

    :param contributions: The sorted list of contributions.
    :effect: Writes the contributions to `contributions.md` in a formatted way.
    """
    category_groups: list[list[str]] = []
    category: str | None = None
    for contribution in contributions:
        if contribution.category != category:
            category = contribution.category
            category_groups.append([category])
        category_groups[-1].append(contribution.url)
    category_strings = (f"# {x[0]}\n\n{"\n".join(x[1:])}" for x in category_groups)
    _CONTRIBUTIONS.write_text("\n\n".join(category_strings) + "\n")


def _slugify(text: str) -> str:
    """Convert a string to a slug suitable for URLs.

    :param text: The input string to slugify.
    :return: A slugified version of the input string.
    """
    return text.lower().replace(" ", "-").replace("_", "-")


def _overwrite_readme(contributions: list[Contribution]) -> None:
    """Overwrite `README.md` with the contributions.

    :param contributions: The sorted list of contributions.
    :effect: Writes the contributions to `README.md` in a formatted way.
    """
    blocks = [_README_HEADER.read_text()]

    headings = sorted({x.category for x in contributions})
    toc_lines = (f"- [{h}](#{_slugify(h)})" for h in headings)
    blocks.append("\n".join(toc_lines))

    heading: str | None = None
    content_lines: list[str] = []
    for contribution in contributions:
        if contribution.category != heading:
            heading = contribution.category
            content_lines.extend(
                [f"\n## {heading}", "", f"|     |     |     |", f"| --- | --- | --- |"]
            )
        columns = (
            f"[{contribution.name}]({contribution.url})",
            contribution.description,
            f"⭐{contribution.stars}",
        )
        content_lines.append(f"| {' | '.join(columns)} |")

    blocks.append("\n".join(content_lines))

    _README.write_text("\n\n---\n\n".join(blocks) + "\n", encoding="utf-8")


def main() -> None:
    """Main function to update the README file."""
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        github_token = input("Enter your GitHub token for api requests: ").strip()
    contributions = _read_contributions(github_token)
    _overwrite_contributions_md(contributions)
    _overwrite_readme(contributions)
    print("done")


if __name__ == "__main__":
    main()
    log_star_milestones()
