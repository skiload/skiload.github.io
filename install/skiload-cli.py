#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


BASE_URL = os.environ.get("SKILOAD_BASE_URL", "https://skiload.com").rstrip("/")
CATALOG_URL = os.environ.get("SKILOAD_CATALOG_URL", f"{BASE_URL}/install/catalog.json")


def fetch_json(url: str):
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "skiload-cli/0.1",
        },
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def fetch_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "skiload-cli/0.1",
        },
    )
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8")


def load_catalog():
    return fetch_json(CATALOG_URL)


def normalize(value: str) -> str:
    return value.strip().lower()


def score_skill(skill, query: str):
    q = normalize(query)
    if not q:
        return (0, 0, 0)

    name = normalize(skill.get("name", ""))
    slug = normalize(skill.get("slug", ""))
    author = normalize(skill.get("author", ""))
    description = normalize(skill.get("descriptionZh") or skill.get("description") or "")
    category = normalize(skill.get("category", ""))
    tags = " ".join(normalize(tag) for tag in skill.get("tags", []))
    haystack = " ".join([name, slug, author, description, category, tags])

    if slug == q or name == q:
        match = 4
    elif slug.startswith(q) or name.startswith(q):
        match = 3
    elif q in slug or q in name:
        match = 2
    elif q in haystack:
        match = 1
    else:
        match = 0

    return (
        match,
        1 if skill.get("featured") else 0,
        int(skill.get("starsValue") or 0),
    )


def find_matches(skills, query: str):
    matches = [skill for skill in skills if score_skill(skill, query)[0] > 0]
    matches.sort(key=lambda item: score_skill(item, query), reverse=True)
    return matches


def pick_skill(skills, query: str):
    matches = find_matches(skills, query)
    return matches[0] if matches else None


def parse_github_repo(url: Optional[str]):
    if not url:
        return None

    parsed = urlparse(url)
    if parsed.netloc != "github.com":
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None

    return {
        "owner": parts[0],
        "repo": parts[1][:-4] if parts[1].endswith(".git") else parts[1],
    }


def build_candidate_paths(skill_path: Optional[str]):
    if not skill_path:
        return ["SKILL.md", "skill.md"]

    cleaned = skill_path.strip("/")
    if cleaned.lower().endswith(".md"):
        if cleaned.lower().endswith("skill.md"):
            return [cleaned]
        return []

    return [f"{cleaned}/SKILL.md", f"{cleaned}/skill.md"]


def resolve_github_artifact(skill):
    repo = parse_github_repo(skill.get("baseRepoUrl"))
    if not repo:
        return {
            "raw_url": None,
            "source_url": skill.get("skillhubUrl"),
        }

    try:
        repo_meta = fetch_json(f"https://api.github.com/repos/{repo['owner']}/{repo['repo']}")
    except (HTTPError, URLError):
        repo_meta = {}

    branch = repo_meta.get("default_branch") or "main"

    for candidate_path in build_candidate_paths(skill.get("skillPath")):
        encoded_path = "/".join(quote(part) for part in candidate_path.split("/"))
        url = (
            f"https://api.github.com/repos/{repo['owner']}/{repo['repo']}"
            f"/contents/{encoded_path}?ref={quote(branch)}"
        )

        try:
            content = fetch_json(url)
        except (HTTPError, URLError):
            continue

        if content.get("type") == "file" and content.get("download_url"):
            return {
                "raw_url": content["download_url"],
                "source_url": content.get("html_url") or skill.get("baseRepoUrl") or skill.get("skillhubUrl"),
            }

    return {
        "raw_url": None,
        "source_url": skill.get("baseRepoUrl") or skill.get("skillhubUrl"),
    }


def build_target(agent: str, slug: str):
    if agent == "codex-cli":
        base = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / slug
    elif agent == "claude-code":
        base = Path.home() / ".claude" / "skills" / slug
    else:
        base = Path.cwd() / "skills" / slug

    return {
        "directory": base,
        "target": base / "SKILL.md",
    }


def cmd_search(args):
    catalog = load_catalog()
    matches = find_matches(catalog.get("skills", []), " ".join(args.query))

    if not matches:
        print("No matching skills found.", file=sys.stderr)
        return 1

    for index, skill in enumerate(matches[: args.limit], start=1):
        stars = skill.get("starsLabel") or skill.get("starsValue") or 0
        print(
            f"{index}. {skill.get('name')} ({skill.get('slug')})"
            f"  by {skill.get('author', 'unknown')}  stars {stars}"
        )
        print(f"   {skill.get('skillhubUrl')}")

    return 0


def cmd_install(args):
    catalog = load_catalog()
    query = " ".join(args.slug_or_query)
    skill = pick_skill(catalog.get("skills", []), query)

    if not skill:
        print("No matching skill found.", file=sys.stderr)
        return 1

    target = build_target(args.agent, skill["slug"])
    artifact = resolve_github_artifact(skill)

    if not artifact["raw_url"]:
        print(f"Could not resolve a downloadable SKILL.md for {skill['slug']}.", file=sys.stderr)
        print(f"Open this source page and install manually: {artifact['source_url']}", file=sys.stderr)
        return 2

    target["directory"].mkdir(parents=True, exist_ok=True)
    content = fetch_text(artifact["raw_url"])
    target["target"].write_text(content, encoding="utf-8")

    print(f"Installed {skill['name']} to {target['target']}")
    print(f"Source: {artifact['source_url']}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="skiload",
        description="Search and install public skills from the Skiload catalog.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search the public catalog")
    search.add_argument("query", nargs="+", help="Keyword or skill name")
    search.add_argument("--limit", type=int, default=10, help="Max rows to print")
    search.set_defaults(func=cmd_search)

    install = subparsers.add_parser("install", help="Install a skill from the public catalog")
    install.add_argument("slug_or_query", nargs="+", help="Slug or keyword")
    install.add_argument(
        "--agent",
        choices=["generic", "codex-cli", "claude-code"],
        default="generic",
        help="Install target",
    )
    install.set_defaults(func=cmd_install)

    return parser


def main():
    try:
        parser = build_parser()
        args = parser.parse_args()
        return args.func(args)
    except HTTPError as error:
        print(f"Request failed: {error.code} {error.reason}", file=sys.stderr)
        return 1
    except URLError as error:
        print(f"Network error: {error.reason}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
