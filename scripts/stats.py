#!/usr/bin/env python3
"""Draws the GitHub activity cards in the profile README.

Every number comes from GitHub's contribution calendar (the green graph on the
profile), fetched through the GraphQL API, so the cards always agree with it.
.github/workflows/profile.yml runs this every 3 hours and publishes dist/ to
the `output` branch. To try it locally:

    GITHUB_TOKEN=$(gh auth token) python3 scripts/stats.py

Each card is written twice, *-dark.svg and *-light.svg, in GitHub's own
colors (Primer tokens), plus stats.md with the same numbers as tables.
"""

import datetime as dt
import json
import os
import urllib.request
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape

LOGIN = os.environ.get("PROFILE_LOGIN", "shiv4006")
OUT = Path(os.environ.get("OUT_DIR", "dist"))
W = 840

THEMES = {
    "dark": {
        "bg": "#0d1117", "tile": "#151b23", "border": "#3d444d", "grid": "#262c36",
        "fg": "#f0f6fc", "muted": "#9198a1", "success": "#3fb950",
        "accent": "#2ea043", "rest": "#656c76", "cell_edge": "rgba(1,4,9,0.05)",
        "levels": ["#151b23", "#033a16", "#196c2e", "#2ea043", "#56d364"],
    },
    "light": {
        "bg": "#ffffff", "tile": "#f6f8fa", "border": "#d1d9e0", "grid": "#e6eaef",
        "fg": "#1f2328", "muted": "#59636e", "success": "#1a7f37",
        "accent": "#2da44e", "rest": "#8c959f", "cell_edge": "rgba(31,35,40,0.05)",
        "levels": ["#eff2f5", "#aceebb", "#4ac26b", "#2da44e", "#116329"],
    },
}
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

CSS = (
    "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif}"
    ".tab{font-variant-numeric:tabular-nums}"
    ".pop{animation:pop .4s ease-out backwards}"
    ".rise{animation:rise .6s ease-out backwards}"
    ".draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.4s ease-out .2s forwards}"
    ".pulse{animation:pulse 2s ease-in-out infinite}"
    "@keyframes pop{from{opacity:0}}"
    "@keyframes rise{from{opacity:0;transform:translateY(4px)}}"
    "@keyframes draw{to{stroke-dashoffset:0}}"
    "@keyframes pulse{50%{opacity:.35}}"
    "@media (prefers-reduced-motion:reduce){.pop,.rise,.pulse{animation:none}.draw{animation:none;stroke-dashoffset:0}}"
)


# ------------------------------------------------------------------ data

def graphql(query, **variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
                 "Content-Type": "application/json", "User-Agent": f"{LOGIN}-profile"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.load(resp)
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]["user"]


def fetch():
    user = graphql("""query($login: String!) { user(login: $login) {
        createdAt
        contributionsCollection {
          contributionYears restrictedContributionsCount totalCommitContributions
          totalPullRequestContributions totalPullRequestReviewContributions
          totalIssueContributions totalRepositoryContributions
          contributionCalendar { totalContributions
            weeks { contributionDays { date contributionCount contributionLevel } } }
        } } }""", login=LOGIN)
    year = user["contributionsCollection"]
    calendar = year["contributionCalendar"]
    weeks = [[{"date": dt.date.fromisoformat(d["date"]), "count": d["contributionCount"],
               "level": LEVELS[d["contributionLevel"]]} for d in w["contributionDays"]]
             for w in calendar["weeks"]]

    # every day since the account was created, one calendar year at a time
    daily = {}
    for y in year["contributionYears"]:
        past = graphql("""query($login: String!, $from: DateTime!, $to: DateTime!) { user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar { weeks { contributionDays { date contributionCount } } } } } }""",
                       login=LOGIN, **{"from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"})
        for w in past["contributionsCollection"]["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                if d["date"].startswith(str(y)):
                    daily[dt.date.fromisoformat(d["date"])] = d["contributionCount"]

    first = weeks[0][0]["date"]
    before = graphql("""query($login: String!, $from: DateTime!, $to: DateTime!) { user(login: $login) {
        contributionsCollection(from: $from, to: $to) { contributionCalendar { totalContributions } } } }""",
                     login=LOGIN, **{"from": f"{first - dt.timedelta(days=365)}T00:00:00Z",
                                     "to": f"{first - dt.timedelta(days=1)}T23:59:59Z"})
    return {
        "created": dt.date.fromisoformat(user["createdAt"][:10]),
        "weeks": weeks,
        "year_total": calendar["totalContributions"],
        "prev_year_total": before["contributionsCollection"]["contributionCalendar"]["totalContributions"],
        "daily": daily,
        "types": {
            "private": year["restrictedContributionsCount"],
            "commits": year["totalCommitContributions"],
            "repos": year["totalRepositoryContributions"],
            "prs": year["totalPullRequestContributions"],
            "issues": year["totalIssueContributions"],
            "reviews": year["totalPullRequestReviewContributions"],
        },
    }


def summarize(data):
    daily, weeks = data["daily"], data["weeks"]
    days = [d for w in weeks for d in w]
    today = days[-1]["date"]
    start = min(data["created"], min(daily))
    span = [start + dt.timedelta(days=i) for i in range((today - start).days + 1)]
    counts = [daily.get(d, 0) for d in span]

    runs, run_start = [], None
    for d, c in zip(span, counts):
        if c and run_start is None:
            run_start = d
        if not c and run_start is not None:
            runs.append((run_start, d - dt.timedelta(days=1)))
            run_start = None
    if run_start is not None:
        runs.append((run_start, today))
    longest = max(runs, key=lambda r: ((r[1] - r[0]).days, r[1]), default=None)
    # like GitHub's streaks: a day without contributions *yet* doesn't break it
    current = next((r for r in runs if r[1] >= today - dt.timedelta(days=1)), None)

    best_day = max(span, key=lambda d: (daily.get(d, 0), d))
    by_weekday = [0] * 7
    for d in days:
        by_weekday[(d["date"].weekday() + 1) % 7] += d["count"]

    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    months.reverse()
    per_month = defaultdict(int)
    for d, c in daily.items():
        per_month[(d.year, d.month)] += c

    per_year = defaultdict(int)
    for d, c in daily.items():
        per_year[d.year] += c

    return {
        "today": today,
        "created": data["created"],
        "weeks": weeks,
        "total": sum(counts),
        "active_total": sum(1 for c in counts if c),
        "year_total": data["year_total"],
        "prev_year_total": data["prev_year_total"],
        "year_days": len(days),
        "year_active": sum(1 for d in days if d["count"]),
        "longest": (longest, (longest[1] - longest[0]).days + 1) if longest else (None, 0),
        "current": (current, (current[1] - current[0]).days + 1) if current else (None, 0),
        "best_day": (best_day, daily.get(best_day, 0)),
        "by_weekday": by_weekday,
        "months": [(ym, per_month[ym]) for ym in months],
        "years": sorted(per_year.items()),
        "types": data["types"],
        "weekly": [sum(d["count"] for d in w) for w in weeks],
    }


# ------------------------------------------------------------------ drawing helpers

def fmt_day(d, year=True):
    return f"{d:%b} {d.day}" + (f", {d.year}" if year else "")


def days(n):
    return f"{n} day" if n == 1 else f"{n} days"


def fmt_range(r):
    a, b = r
    if a == b:
        return fmt_day(a)
    if a.year == b.year:
        return f"{fmt_day(a, False)} – {fmt_day(b)}"
    return f"{fmt_day(a)} – {fmt_day(b)}"


def nice_ticks(top, count=4):
    step = 1
    for mag in (1, 10, 100, 1000, 10000):
        for base in (1, 2, 5):
            if base * mag * count >= top:
                step = base * mag
                break
        else:
            continue
        break
    ticks = [0]
    while ticks[-1] < top:
        ticks.append(ticks[-1] + step)
    return ticks


class Svg:
    def __init__(self, t, height):
        self.t, self.h, self.parts = t, height, []

    def add(self, markup):
        self.parts.append(markup)

    def text(self, x, y, content, size=12, color="muted", weight=400, anchor="start", cls="", attrs=""):
        """content: a string, or (text, color key, size, weight) runs."""
        if isinstance(content, str):
            content = [(content, color, size, weight)]
        spans = "".join(f'<tspan fill="{self.t[c]}" font-size="{s}" font-weight="{wt}">{escape(tx)}</tspan>'
                        for tx, c, s, wt in content)
        cls = f' class="{cls}"' if cls else ""
        anchor = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}"{anchor}{cls}{attrs}>{spans}</text>')

    def title(self, x, y, title, sub=None):
        self.text(x, y, title, 14, "fg", 600)
        if sub:
            self.text(x, y + 18, sub, 12)

    def column(self, x, base, w, h, color, r=4, attrs=""):
        """A column with a rounded data end and a square baseline."""
        r = min(r, h, w / 2)
        top = base - h
        self.add(f'<path d="M{x:.1f} {base:.1f}V{top + r:.1f}Q{x:.1f} {top:.1f} {x + r:.1f} {top:.1f}'
                 f'H{x + w - r:.1f}Q{x + w:.1f} {top:.1f} {x + w:.1f} {top + r:.1f}V{base:.1f}Z" '
                 f'fill="{color}"{attrs}/>')

    def bar(self, x, y, w, h, color, r=4, attrs=""):
        """A horizontal bar with a rounded data end and a square baseline."""
        r = min(r, w, h / 2)
        self.add(f'<path d="M{x:.1f} {y:.1f}H{x + w - r:.1f}Q{x + w:.1f} {y:.1f} {x + w:.1f} {y + r:.1f}'
                 f'V{y + h - r:.1f}Q{x + w:.1f} {y + h:.1f} {x + w - r:.1f} {y + h:.1f}H{x:.1f}Z" '
                 f'fill="{color}"{attrs}/>')

    def hline(self, x1, x2, y, color="grid"):
        self.add(f'<path d="M{x1:.1f} {y + .5:.1f}H{x2:.1f}" stroke="{self.t[color]}"/>')

    def render(self, label):
        t = self.t
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.h}" viewBox="0 0 {W} {self.h}" '
                f'role="img" aria-label="{escape(label)}"><style>{CSS}</style>'
                f'<rect x=".5" y=".5" width="{W - 1}" height="{self.h - 1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>'
                f'{"".join(self.parts)}</svg>')


# ------------------------------------------------------------------ cards

def header(s, t):
    g = Svg(t, 212)
    g.text(32, 66, "Shivam Kumar", 34, "fg", 700, cls="rise")
    g.text(32, 98, [("Full-Stack Developer", "fg", 18, 500), ("  ·  CypherSOL Fintech", "muted", 18, 400)], cls="rise")
    g.text(32, 130, "I build fintech & forensic software: fraud detection, bank-statement", 14, cls="rise")
    g.text(32, 150, "forensics, invoicing and GST reconciliation. Based in India.", 14, cls="rise")
    g.add(f'<circle class="pulse" cx="38" cy="177" r="4" fill="{t["success"]}"/>')
    g.text(50, 181, "Open to full-stack roles and interesting problems", 12, "fg", 500)

    # the last year as a weekly sparkline
    x0, x1, top, base = 548, 808, 112, 166
    g.text(x0, 52, "Last year on GitHub", 12)
    g.text(x0, 84, [(f"{s['year_total']:,}", "fg", 28, 600), ("  contributions", "muted", 14, 400)])
    weekly = s["weekly"]
    peak = max(weekly) or 1
    pts = [(x0 + (x1 - x0) * i / (len(weekly) - 1), base - (base - top) * v / peak) for i, v in enumerate(weekly)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    g.add(f'<path d="M{x0} {base}L{line.replace(" ", "L")}L{x1} {base}Z" fill="{t["accent"]}" fill-opacity=".1"/>')
    g.add(f'<polyline class="draw" pathLength="1" points="{line}" fill="none" stroke="{t["accent"]}" '
          f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    ex, ey = pts[-1]
    g.add(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="{t["accent"]}" stroke="{t["bg"]}" stroke-width="2"/>')
    g.hline(x0, x1, base)
    g.text(x0, 188, f"{s['year_active']} active days  ·  per week, last 12 months", 12)
    return g.render(f"Shivam Kumar, Full-Stack Developer at CypherSOL Fintech. {s['year_total']} contributions in the last year.")


def overview(s, t):
    g = Svg(t, 292)
    g.title(24, 38, "Contribution overview", f"From GitHub's contribution calendar, since joining in {s['created']:%b %Y}")
    g.text(W - 24, 38, f"Updated {fmt_day(s['today'])}", 12, anchor="end")

    prev, cur = s["prev_year_total"], s["year_total"]
    if prev and cur >= 2 * prev:
        delta = f"↑ {cur / prev:.1f}× the year before"
    elif prev:
        delta = f"{'↑' if cur >= prev else '↓'} {abs(cur - prev) / prev:.0%} vs the year before"
    else:
        delta = "first full year"
    (cur_run, cur_len), (long_run, long_len) = s["current"], s["longest"]
    best, best_n = s["best_day"]
    tiles = [
        ("Contributions in the last year", f"{cur:,}", "", delta, "success" if cur >= prev else "muted"),
        ("Total contributions", f"{s['total']:,}", "", f"since {fmt_day(s['created'])}", "muted"),
        ("Active days", f"{s['year_active']}", f" of {s['year_days']}",
         f"in the last year  ·  {s['active_total']} in total", "muted"),
        ("Current streak", f"{cur_len}", " day" if cur_len == 1 else " days",
         fmt_range(cur_run) if cur_run else "starts with the next contribution", "muted"),
        ("Longest streak", f"{long_len}", " day" if long_len == 1 else " days",
         fmt_range(long_run) if long_run else "–", "muted"),
        ("Best day", f"{best_n}", " contributions", f"{best:%A}, {fmt_day(best)}", "muted"),
    ]
    tw, th, gap = (W - 48 - 24) / 3, 96, 12
    for i, (label, value, unit, sub, sub_color) in enumerate(tiles):
        x, y = 24 + (i % 3) * (tw + gap), 70 + (i // 3) * (th + gap)
        g.add(f'<g class="rise" style="animation-delay:{i * 0.06:.2f}s">')
        g.add(f'<rect x="{x:.1f}" y="{y}" width="{tw:.1f}" height="{th}" rx="8" fill="{t["tile"]}"/>')
        g.text(x + 16, y + 26, label, 12)
        g.text(x + 16, y + 62, [(value, "fg", 30, 600), (unit, "muted", 14, 400)])
        g.text(x + 16, y + 84, sub, 12, sub_color)
        g.add("</g>")
    return g.render(f"{cur} contributions in the last year, {s['total']} in total, {s['year_active']} active days "
                    f"in the last year, current streak {cur_len} days, longest streak {long_len} days.")


def calendar(s, t):
    g = Svg(t, 232)
    weeks = s["weeks"]
    g.title(24, 38, f"{s['year_total']:,} contributions in the last year")
    g.text(W - 24, 38, f"{s['year_active']} active days", 12, anchor="end")
    pitch, cell = 14, 11
    grid_w = len(weeks) * pitch - (pitch - cell)
    gx = (W - (30 + grid_w)) / 2 + 30
    gy = 84
    # like GitHub: a month is labelled over the first column it starts, unless it would crowd the next label
    starts = [i for i, w in enumerate(weeks) if i == 0 or w[0]["date"].month != weeks[i - 1][0]["date"].month]
    for i, col in enumerate(starts):
        if i + 1 < len(starts) and starts[i + 1] - col < 3:
            continue
        g.text(gx + col * pitch, gy - 10, f"{weeks[col][0]['date']:%b}", 11)
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        g.text(gx - 8, gy + row * pitch + 9, name, 11, anchor="end")
    for i, week in enumerate(weeks):
        for d in week:
            row = (d["date"].weekday() + 1) % 7
            g.add(f'<rect class="pop" style="animation-delay:{i * 0.012:.3f}s" x="{gx + i * pitch:.1f}" '
                  f'y="{gy + row * pitch}" width="{cell}" height="{cell}" rx="2" fill="{t["levels"][d["level"]]}" '
                  f'stroke="{t["cell_edge"]}"/>')
    by_weekday = s["by_weekday"]
    (by, bm), bn = max(s["months"], key=lambda m: m[1])
    busiest = WEEKDAYS[by_weekday.index(max(by_weekday))]
    foot = gy + 7 * pitch + 24
    g.text(gx - 30, foot, f"Most active on {busiest}s  ·  busiest month: {dt.date(by, bm, 1):%B %Y}", 12)
    lx = gx + grid_w - 5 * pitch - 30
    g.text(lx - 8, foot, "Less", 11, anchor="end")
    for lvl in range(5):
        g.add(f'<rect x="{lx + lvl * pitch:.1f}" y="{foot - 10}" width="{cell}" height="{cell}" rx="2" '
              f'fill="{t["levels"][lvl]}" stroke="{t["cell_edge"]}"/>')
    g.text(lx + 5 * pitch + 4, foot, "More", 11)
    return g.render(f"Contribution calendar: {s['year_total']} contributions on {s['year_active']} days in the last year.")


def rhythm(s, t):
    g = Svg(t, 268)
    months = s["months"]
    g.title(24, 38, "Contributions per month",
            f"{dt.date(*months[0][0], 1):%b %Y} – {dt.date(*months[-1][0], 1):%b %Y} (this month so far)")
    px0, px1, top, base = 60, 500, 86, 222
    ticks = nice_ticks(max(v for _, v in months) or 1)
    scale = (base - top) / ticks[-1]
    for v in ticks:
        y = base - v * scale
        g.hline(px0, px1, y)
        g.text(px0 - 10, y + 4, f"{v:,}", 11, anchor="end", cls="tab")
    band = (px1 - px0) / len(months)
    cw = min(24, band * 0.6)
    peak = max(range(len(months)), key=lambda i: months[i][1])
    for i, ((y, m), v) in enumerate(months):
        x = px0 + i * band + (band - cw) / 2
        if v:
            g.column(x, base, cw, v * scale, t["accent"],
                     attrs=f' class="rise" style="animation-delay:{i * 0.04:.2f}s"')
        g.text(x + cw / 2, base + 18, f"{dt.date(y, m, 1):%b}", 11, anchor="middle")
        if i in (peak, len(months) - 1) and v:
            g.text(x + cw / 2, base - v * scale - 6, f"{v:,}", 12, "fg", 600, anchor="middle")
    g.add(f'<path d="M{px0} {base + .5}H{px1}" stroke="{t["border"]}"/>')

    # by weekday: the busiest day in green, the rest in gray
    x0 = 548
    by_weekday = s["by_weekday"]
    best = by_weekday.index(max(by_weekday))
    g.title(x0, 38, "By day of the week", f"Last year  ·  busiest: {WEEKDAYS[best]}")
    bx, bw_max = x0 + 40, W - 24 - (x0 + 40) - 40
    peak_v = max(by_weekday) or 1
    for i, v in enumerate(by_weekday):
        y = 82 + i * 22
        g.text(x0, y + 11, WEEKDAYS[i][:3], 12)
        w = bw_max * v / peak_v
        if v:
            g.bar(bx, y, w, 14, t["accent"] if i == best else t["rest"],
                  attrs=f' class="rise" style="animation-delay:{i * 0.05:.2f}s"')
        g.text(bx + w + 6, y + 11, f"{v:,}", 12, "fg" if i == best else "muted", 600 if i == best else 400, cls="tab")
    return g.render("Contributions per month for the last 12 months, and by day of the week.")


def years(s, t):
    g = Svg(t, 252)
    g.title(24, 38, "Contributions by year", f"Since joining GitHub in {s['created']:%B %Y}")
    yrs = s["years"]
    px0, px1, top, base = 24, 400, 98, 206
    peak = max(v for _, v in yrs) or 1
    band = (px1 - px0) / len(yrs)
    cw = 24
    for i, (y, v) in enumerate(yrs):
        x = px0 + i * band + (band - cw) / 2
        h = (base - top) * v / peak
        if v:
            g.column(x, base, cw, h, t["accent"], attrs=f' class="rise" style="animation-delay:{i * 0.08:.2f}s"')
        g.text(x + cw / 2, base - h - 8, f"{v:,}", 13, "fg", 600, anchor="middle")
        g.text(x + cw / 2, base + 20, str(y) + (" so far" if y == s["today"].year else ""), 12, anchor="middle")
    g.add(f'<path d="M{px0} {base + .5}H{px1}" stroke="{t["border"]}"/>')

    x0, x1 = 448, W - 24
    types = s["types"]
    total = sum(types.values()) or 1
    share = types["private"] / total
    g.title(x0, 38, "Private and public work", "Last year  ·  GitHub counts private contributions without details")
    g.text(x0, 112, [(f"{share:.0%}", "fg", 30, 600), ("  in private repositories", "muted", 14, 400)])
    g.add(f'<rect x="{x0}" y="126" width="{x1 - x0}" height="8" rx="4" fill="{t["levels"][1]}"/>')
    g.add(f'<rect class="rise" x="{x0}" y="126" width="{(x1 - x0) * share:.1f}" height="8" rx="4" fill="{t["accent"]}"/>')
    rows = [(types["private"], "private contributions"), (types["commits"], "commits to public repositories"),
            (types["repos"], "repositories created"), (types["prs"], "pull requests"),
            (types["reviews"], "code reviews"), (types["issues"], "issues opened")]
    y = 166
    for n, label in [r for r in rows if r[0]][:4]:
        g.text(x0, y, [(f"{n:,}", "fg", 14, 600), (f"  {label}", "muted", 13, 400)])
        y += 22
    return g.render(f"Contributions by year; {share:.0%} of last year's contributions were in private repositories.")


def table_view(s):
    (cur_run, cur_len), (long_run, long_len) = s["current"], s["longest"]
    best, best_n = s["best_day"]
    lines = [
        f"# Contribution numbers for @{LOGIN}",
        "",
        f"Updated {fmt_day(s['today'])} from GitHub's contribution calendar.",
        "",
        "| | |", "|---|---|",
        f"| Contributions in the last year | {s['year_total']:,} |",
        f"| Contributions in the year before | {s['prev_year_total']:,} |",
        f"| Total contributions since {fmt_day(s['created'])} | {s['total']:,} |",
        f"| Active days in the last year | {s['year_active']} of {s['year_days']} |",
        f"| Active days in total | {s['active_total']} |",
        f"| Current streak | {days(cur_len)}{f' ({fmt_range(cur_run)})' if cur_run else ''} |",
        f"| Longest streak | {days(long_len)}{f' ({fmt_range(long_run)})' if long_run else ''} |",
        f"| Best day | {best_n} on {fmt_day(best)} |",
        "", "## Per month", "", "| Month | Contributions |", "|---|---:|",
        *[f"| {dt.date(y, m, 1):%B %Y} | {v:,} |" for (y, m), v in s["months"]],
        "", "## By day of the week (last year)", "", "| Day | Contributions |", "|---|---:|",
        *[f"| {WEEKDAYS[i]} | {v:,} |" for i, v in enumerate(s["by_weekday"])],
        "", "## Per year", "", "| Year | Contributions |", "|---|---:|",
        *[f"| {y} | {v:,} |" for y, v in s["years"]],
        "", "## Last year by type", "", "| Type | Count |", "|---|---:|",
        *[f"| {k} | {v:,} |" for k, v in s["types"].items()],
    ]
    return "\n".join(lines) + "\n"


def main():
    s = summarize(fetch())
    OUT.mkdir(parents=True, exist_ok=True)
    for name, card in (("header", header), ("overview", overview), ("calendar", calendar),
                       ("rhythm", rhythm), ("years", years)):
        for theme, t in THEMES.items():
            (OUT / f"{name}-{theme}.svg").write_text(card(s, t))
    (OUT / "stats.md").write_text(table_view(s))
    print(f"{s['year_total']} contributions in the last year, {s['total']} in total, "
          f"{s['year_active']} active days, longest streak {s['longest'][1]}")


if __name__ == "__main__":
    main()
