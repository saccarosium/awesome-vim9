"""Update the README file to reflect `contributions.md`.

# For links like https://github.com/habamax/.vim or https://codeberg.org/owner/repo
- Query the GitHub or Codeberg API to get the description and star count for each
  repository listed in `contributions.md`.
- Lay this information out in the README file.
- Format and sort `contributions.md`.

# For links like https://github.com/vim/vim/tree/master/runtime/pack/dist/opt/cfilter
- set description to a f":h package-{Path(repo_url).stem}"
- set star count to __N/A__

The user does not need to run this script. Just update `contributions.md` and submit
a pull request.

:author: Shay Hill
:created: 2025-07-28
"""

import dataclasses
import datetime
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import requests

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


# ==============================================================================
#
#   Star milestone tracking
#
# ==============================================================================


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
            if anchor != sub_anchor:  # an addition, not a replacement
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


# ==============================================================================
#
#   Update description and star count for each contribution
#
# ==============================================================================


def _parse_repo_url(repo_url: str) -> tuple[str, str, str]:
    """Parse a repository URL into host, owner, and repo.

    :param repo_url: Repository URL (e.g. https://github.com/owner/repo or
        https://codeberg.org/owner/repo)
    :return: Tuple of (host, owner, repo)
    :raises ValueError: If the URL is not in the expected format.
    """
    supported_hosts = ("github.com", "codeberg.org")
    try:
        parts = repo_url.rstrip("/").split("/")
        host_index = next(
            (i for i, p in enumerate(parts) if p in supported_hosts),
            -1,
        )
        if host_index < 0:
            msg = (
                f"Unsupported repository host. Expected one of {supported_hosts}. "
                f"Got '{repo_url}'"
            )
            raise ValueError(msg)
        host = parts[host_index]
        owner = parts[host_index + 1]
        repo = parts[host_index + 2]
    except IndexError as e:
        msg = (
            "Invalid repository URL format. "
            f"Expected: 'https://github.com/owner/repo' or 'https://codeberg.org/owner/repo'. "
            f"Got '{repo_url}'"
        )
        raise ValueError(msg) from e

    return host, owner, repo


def _get_api_url_from_repo_url(repo_url: str) -> str:
    """Format a repository URL into the API URL.

    :param repo_url: Repository URL (GitHub or Codeberg)
    :return: The formatted API URL for the appropriate service
    :raises ValueError: If the URL is not in the expected format.
    """
    host, owner, repo = _parse_repo_url(repo_url)
    if host == "github.com":
        return f"https://api.github.com/repos/{owner}/{repo}"
    if host == "codeberg.org":
        return f"https://codeberg.org/api/v1/repos/{owner}/{repo}"
    msg = f"Unsupported host: {host}"
    raise ValueError(msg)


@dataclasses.dataclass
class RepoInfo:
    """Hold description and star count for a code hosting service repository."""

    description: str
    stars: int | None


@dataclasses.dataclass
class _Tokens:
    """API tokens for supported code hosting services."""

    github: str
    codeberg: str


def _get_repo_info(repo_url: str, tokens: _Tokens) -> RepoInfo:
    """Get repository information from GitHub or Codeberg API.

    :param repo_url: Repository URL (GitHub or Codeberg)
    :param tokens: API tokens for authentication
    :return: Repository description and star count
    """
    host, owner, repo = _parse_repo_url(repo_url)
    api_url = _get_api_url_from_repo_url(repo_url)

    if host == "github.com":
        headers = {
            "Authorization": f"token {tokens.github}",
            "Accept": "application/vnd.github.v3+json",
        }
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        description = data.get("description") or "*No description provided.*"
        stars = data.get("stargazers_count")
    else:
        headers = {
            "Authorization": f"token {tokens.codeberg}",
            "Accept": "application/json",
        }
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        description = data.get("description") or "*No description provided.*"
        stars = data.get("stars_count")

    if description == "The official Vim repository":
        description = f":h package-{Path(repo_url).stem}"
        stars = None

    return RepoInfo(description, stars)


@dataclasses.dataclass(order=False)
class Contribution:
    """Readme table column information for a contribution."""

    category: str
    url: str
    tokens: _Tokens = dataclasses.field(repr=False, compare=False)

    def __post_init__(self) -> None:
        """Post-initialization processing."""
        self.__repo_info: RepoInfo | None = None
        _, self._owner, self._repo = _parse_repo_url(self.url)

    @property
    def name(self) -> str:
        """Get the name of the contribution."""
        return f"{self._owner}/{self._repo}"

    @property
    def _repo_info(self) -> RepoInfo:
        """Get the repository information, caching it."""
        if self.__repo_info is None:
            self.__repo_info = _get_repo_info(self.url, self.tokens)
        return self.__repo_info

    @property
    def description(self) -> str:
        """Get the description of the repository."""
        return self._repo_info.description

    @property
    def stars(self) -> int:
        """Get the number of stars for the repository."""
        return self._repo_info.stars

    def __lt__(self, other: "Contribution") -> bool:
        """Compare contributions by stars."""
        comp_a = (self.category, self._repo.lower(), self._owner.lower(), self.url)
        comp_b = (other.category, other._repo.lower(), other._owner.lower(), other.url)
        return comp_a < comp_b


def _read_contributions(tokens: _Tokens) -> list[Contribution]:
    """Read and format `contributions.md` into a sorted list.

    :param tokens: API tokens for GitHub and Codeberg
    :return: Sorted list of contributions
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
    return sorted([Contribution(x[0], x[1], tokens) for x in contributions])


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
    category_strings = (f"# {x[0]}\n\n{'\n'.join(x[1:])}" for x in category_groups)
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
                [f"\n## {heading}", "", "|     |     |     |", "| --- | --- | --- |"]
            )
        if contribution.description.startswith(":h "):
            description = f"vim/.../pack/.../{Path(contribution.url).stem}"
        else:
            description = contribution.name
        columns = (
            f"[{description}]({contribution.url})",
            contribution.description,
            f"⭐{contribution.stars}" if contribution.stars is not None else "__N/A__",
        )
        content_lines.append(f"| {' | '.join(columns)} |")

    blocks.append("\n".join(content_lines))

    _README.write_text("\n\n---\n\n".join(blocks) + "\n", encoding="utf-8")


def main() -> None:
    """Main function to update the README file."""
    github_token = os.getenv("GITHUB_TOKEN")
    codeberg_token = os.getenv("CODEBERG_TOKEN")
    if github_token is None:
        github_token = input("Enter your GitHub token for api requests: ").strip()
    if codeberg_token is None:
        codeberg_token = input("Enter your Codeberg token for api requests: ").strip()
    tokens = _Tokens(github=github_token, codeberg=codeberg_token)
    contributions = _read_contributions(tokens)
    _overwrite_contributions_md(contributions)
    _overwrite_readme(contributions)
    print("done")


if __name__ == "__main__":
    main()
    log_star_milestones()
