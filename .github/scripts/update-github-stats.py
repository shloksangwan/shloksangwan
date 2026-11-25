#!/usr/bin/env python3
"""Update the GitHub stats in the profile banner: public repos, contributions and the graph.

Elements it fills in:
  id="gh-repos"          first number -> public repositories I own
  id="gh-contrib"        first number -> contributions in the last 12 months
  id="gh-contrib-total"  first number -> the same total, in the graph's caption
  id="gh-graph"          the <g> whose 13x13 cells are redrawn from the contribution calendar

Needs a token in GH_TOKEN (the workflow's GITHUB_TOKEN is enough, since the data is public).
If GitHub can't be reached, the file is left as it is.

Usage: python3 update-github-stats.py FILE [FILE ...]
"""

import json
import os
import re
import sys
import urllib.request

USER = "shloksangwan"
LEVEL_COLOURS = {
    "NONE": "#111a2b",
    "FIRST_QUARTILE": "#0c2d6b",
    "SECOND_QUARTILE": "#1f6feb",
    "THIRD_QUARTILE": "#58a6ff",
    "FOURTH_QUARTILE": "#a5d6ff",
}
QUERY = """query($login: String!) {
  user(login: $login) {
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER) { totalCount }
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { weekday contributionLevel } }
      }
    }
  }
}"""


def fetch_stats():
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("set GH_TOKEN")
    body = json.dumps({"query": QUERY, "variables": {"login": USER}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body, headers={
        "Authorization": f"bearer {token}", "Content-Type": "application/json",
        "User-Agent": "github-stats-updater"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    if data.get("errors"):
        raise RuntimeError(data["errors"][0].get("message", "GraphQL error"))
    user = data["data"]["user"]
    calendar = user["contributionsCollection"]["contributionCalendar"]
    return user["repositories"]["totalCount"], calendar["totalContributions"], calendar["weeks"]


def graph_cells(weeks):
    cells = []
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            colour = LEVEL_COLOURS.get(day["contributionLevel"], LEVEL_COLOURS["NONE"])
            cells.append(f'<rect x="{col * 16}" y="{day["weekday"] * 16}" width="13" height="13" rx="3" fill="{colour}"/>')
    return "".join(cells)


def set_number(text, element_id, value):
    pattern = re.compile(r'(<(\w+)\b[^>]*\bid="%s"[^>]*>)([^<]*)(</\2>)' % element_id)
    return pattern.sub(lambda m: m.group(1) + re.sub(r"\d+", str(value), m.group(3), count=1) + m.group(4), text)


def main(paths):
    try:
        repos, total, weeks = fetch_stats()
    except Exception as err:  # keep the old numbers rather than fail the run
        print(f"warning: could not fetch GitHub stats: {err}", file=sys.stderr)
        return
    print(f"public repos: {repos}, contributions: {total}, weeks: {len(weeks)}")

    for path in paths:
        with open(path, encoding="utf-8") as f:
            text = original = f.read()
        text = set_number(text, "gh-repos", repos)
        text = set_number(text, "gh-contrib", total)
        text = set_number(text, "gh-contrib-total", total)
        # Replace the run of cells at the start of the graph group, keeping anything after it
        text = re.sub(r'(<g\b[^>]*\bid="gh-graph"[^>]*>)(?:<rect x="\d+" y="\d+" width="13" height="13" rx="3" fill="#[0-9a-f]{6}"/>)+',
                      lambda m: m.group(1) + graph_cells(weeks), text, count=1)
        if text != original:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"updated {path}")


if __name__ == "__main__":
    main(sys.argv[1:])
