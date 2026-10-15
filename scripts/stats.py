#!/usr/bin/env python3
"""Draws the cards in the profile README: the header, now/next, building with
AI, and the GitHub activity graphs.

Every activity number comes from GitHub's contribution calendar (the green
graph on the profile), fetched through the GraphQL API, so the cards always
agree with it.
.github/workflows/profile.yml runs this every 3 hours and publishes dist/ to
the `output` branch. To try it locally:

    GITHUB_TOKEN=$(gh auth token) python3 scripts/stats.py

Each card is written twice, *-dark.svg and *-light.svg, in GitHub's own
colors (Primer tokens), plus stats.md with the same numbers as tables.
"""

import datetime as dt
import functools
import json
import os
import random
import re
import textwrap
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
        "key": "#79c0ff", "live": "#56d364", "dots": "#3d444d",
        "accent": "#2ea043", "rest": "#656c76", "cell_edge": "rgba(1,4,9,0.05)",
        "levels": ["#151b23", "#033a16", "#196c2e", "#2ea043", "#56d364"],
    },
    "light": {
        "bg": "#ffffff", "tile": "#f6f8fa", "border": "#d1d9e0", "grid": "#e6eaef",
        "fg": "#1f2328", "muted": "#59636e", "success": "#1a7f37",
        "key": "#0550ae", "live": "#1a7f37", "dots": "#c8d1da",
        "accent": "#2da44e", "rest": "#8c959f", "cell_edge": "rgba(31,35,40,0.05)",
        "levels": ["#eff2f5", "#aceebb", "#4ac26b", "#2da44e", "#116329"],
    },
}
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
ICON_PACKAGES = {"lobe": "@lobehub/icons-static-svg@1.91.0", "si": "simple-icons@16.30.0"}
CDNS = ["https://cdn.jsdelivr.net/npm/{}/icons/{}.svg", "https://unpkg.com/{}/icons/{}.svg"]
PATH_DATA = r"[MmZzLlHhVvCcSsQqTtAaEe0-9.,\s+-]+"

# ------------------------------------------------------------------ words (edit these)

HERO = [
    ("Role", "Full-Stack Developer"),
    ("Company", "CypherSOL Fintech"),
    ("Built with AI", "assistants · RAG · search · voice"),
    ("Learning", "LLMs · Generative AI · RAG · agents"),
    ("AI tools", "Claude · ChatGPT · Codex · Hugging Face"),
    ("Stack", "TypeScript · React · Next.js · NestJS"),
]
NOW = [
    "Full-stack on six fintech & forensic products",
    "Building AI into forensic tools at CypherSOL",
    "Learning LLMs, generative AI and RAG hands-on",
]
AMBITION = [
    "Grow from full-stack developer to AI engineer",
    "Build generative AI products end to end",
    "Bring LLM agents to fintech & fraud investigation",
]
# (stage, status, [(topic, terms)])
JOURNEY = [
    ("Built with", "done", [
        ("LLM APIs & streaming", "Azure OpenAI · Gemini · SSE"),
        ("Embeddings & vector search", "Transformers · ChromaDB"),
        ("RAG pipelines", "LlamaIndex · BGE · gpt-oss"),
        ("Real-time voice AI", "Gemini Live · speech"),
    ]),
    ("Learning now", "in progress", [
        ("LLM fundamentals", "transformers · attention · tokens"),
        ("Prompt engineering", "few-shot · structured output"),
        ("Advanced RAG", "chunking · reranking · hybrid"),
        ("Generative AI", "text · image · multimodal"),
    ]),
    ("Up next", "planned", [
        ("AI agents", "tool use · MCP · multi-agent"),
        ("Fine-tuning", "LoRA · PEFT · datasets"),
        ("Evals & guardrails", "LLM-as-judge · safety"),
        ("LLMOps", "serving · monitoring · cost"),
    ]),
]
# (name, where, what it does, built with)
AI_BUILDS = [
    ("In-app AI assistant", "at CypherSOL", "Streams answers inside a forensic app, with page context",
     ["React", "SSE"]),
    ("AI avatar presenter", "at Bytical", "Narrates slides and answers audience questions live",
     ["Azure OpenAI", "Speech SDK"]),
    ("RAG over documents", "shiv4006/rag-app", "Ask questions across your own documents",
     ["LlamaIndex", "gpt-oss", "Streamlit"]),
    ("Semantic site search", "shiv4006/smarter-wcs", "Search any website by meaning, not keywords",
     ["Transformers", "ChromaDB", "FastAPI"]),
    ("Real-time voice agent", "shiv4006/gemini-voice-interface", "Low-latency voice conversations you can interrupt",
     ["Gemini Live", "WebSockets"]),
]
SHIPPED_CONCEPTS = ["LLM APIs", "streaming", "embeddings", "vector DB", "RAG", "speech", "real-time"]
# (row label, [(icon, name)]); icons are "lobe:<name>" (LobeHub) or "si:<name>" (Simple Icons)
TOOLKIT = [
    ("AI assistants", [("lobe:claude", "Claude"), ("lobe:claudecode", "Claude Code"), ("lobe:openai", "ChatGPT"),
                       ("lobe:codex", "Codex"), ("lobe:gemini", "Gemini")]),
    ("Models & frameworks", [("lobe:huggingface", "Hugging Face"), ("lobe:llamaindex", "LlamaIndex"),
                             ("lobe:azure", "Azure OpenAI"), ("lobe:nebius", "Nebius AI"), ("si:streamlit", "Streamlit")]),
]
TOOLKIT_MORE = "Sentence Transformers · ChromaDB · BGE embeddings · gpt-oss · FastAPI"

CSS = (
    "text{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif}"
    ".mono{font-family:ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace;white-space:pre}"
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


def since(a, b):
    months = (b.year - a.year) * 12 + b.month - a.month - (b.day < a.day)
    y, m = divmod(months, 12)
    parts = ([f"{y} year{'s' * (y != 1)}"] if y else []) + ([f"{m} month{'s' * (m != 1)}"] if m else [])
    return ", ".join(parts) or "this month"


def wrap(text, chars):
    return textwrap.wrap(text, chars, break_on_hyphens=False)


def shade(color, k):
    return "#" + "".join(f"{int(int(color[i:i + 2], 16) * k):02x}" for i in (1, 3, 5))


@functools.lru_cache(maxsize=None)
def icon_shape(spec):
    """(fill-rule, paths) of a 24x24 icon such as "lobe:openai", or None if it can't be fetched."""
    source, name = spec.split(":")
    svg = ""
    for cdn in CDNS:
        try:
            with urllib.request.urlopen(cdn.format(ICON_PACKAGES[source], name), timeout=30) as resp:
                svg = resp.read().decode()
        except OSError:
            continue
        if "<svg" in svg[:200]:
            break
    paths = re.findall(r'<path\b[^>]*\sd="([^"]+)"', svg)
    if 'viewBox="0 0 24 24"' not in svg or not paths or not all(re.fullmatch(PATH_DATA, d) for d in paths):
        return None
    return ("evenodd" if 'fill-rule="evenodd"' in svg else "nonzero"), tuple(paths)


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

    def icon(self, spec, x, y, size, color):
        shape = icon_shape(spec)
        if shape:
            rule, paths = shape
            body = "".join('<path d="%s"/>' % d for d in paths)
            self.add(f'<g transform="translate({x:.1f} {y:.1f}) scale({size / 24:.4f})" fill="{color}" '
                     f'fill-rule="{rule}">{body}</g>')

    def hline(self, x1, x2, y, color="grid"):
        self.add(f'<path d="M{x1:.1f} {y + .5:.1f}H{x2:.1f}" stroke="{self.t[color]}"/>')

    def render(self, label):
        t = self.t
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{self.h}" viewBox="0 0 {W} {self.h}" '
                f'role="img" aria-label="{escape(label)}"><style>{CSS}</style>'
                f'<rect x=".5" y=".5" width="{W - 1}" height="{self.h - 1}" rx="12" fill="{t["bg"]}" stroke="{t["border"]}"/>'
                f'{"".join(self.parts)}</svg>')


# ------------------------------------------------------------------ cards

def hero(s, t):
    g = Svg(t, 368)
    # left: a small neural network with signals running through it
    layers, xs = [4, 6, 6, 3], [62, 124, 186, 248]
    nodes = [[(x, 176 + (j - (n - 1) / 2) * 42) for j in range(n)] for x, n in zip(xs, layers)]
    for a, b in zip(nodes, nodes[1:]):
        for x1, y1 in a:
            for x2, y2 in b:
                g.add(f'<path d="M{x1} {y1:.1f}L{x2} {y2:.1f}" stroke="{t["border"]}" stroke-opacity=".7"/>')
    rnd = random.Random(LOGIN)
    for i in range(12):
        path = "M" + "L".join(f"{x} {y:.1f}" for x, y in (rnd.choice(layer) for layer in nodes))
        timing = f'dur="2.4s" begin="{i * 0.4:.1f}s" repeatCount="indefinite"'
        g.add(f'<circle r="3" fill="{t["live"]}" opacity="0"><animateMotion path="{path}" {timing}/>'
              f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;.15;.85;1" {timing}/></circle>')
    for li, layer in enumerate(nodes):
        for j, (x, y) in enumerate(layer):
            g.add(f'<circle cx="{x}" cy="{y:.1f}" r="9" fill="{t["tile"]}" stroke="{t["accent"]}" stroke-width="1.5"/>')
            g.add(f'<circle class="pulse" style="animation-delay:{li * 0.3 + j * 0.2:.1f}s" cx="{x}" cy="{y:.1f}" '
                  f'r="3.5" fill="{t["live"]}"/>')
    g.text(155, 336, "// learning & building with AI", 12, cls="mono", anchor="middle")

    # right: a neofetch-style readout, the GitHub half live
    width = 56

    def row(key, value, live=False):
        dots = "." * max(2, width - len(key) - len(value) - 2)
        return [(key, "key", 14, 400), (f" {dots} ", "dots", 14, 400),
                (value, "live" if live else "fg", 14, 600 if live else 400)]

    cur_len, long_len = s["current"][1], s["longest"][1]
    rows = [
        [("shivam", "live", 14, 700), ("@", "muted", 14, 400), ("github", "live", 14, 700)],
        [("─" * width, "dots", 14, 400)],
        *[row(k, v) for k, v in HERO],
        None,
        [("— GitHub ", "muted", 14, 600), ("─" * (width - 9), "dots", 14, 400)],
        row("Contributions", f"{s['year_total']:,} last year · {s['total']:,} total", True),
        row("Active days", f"{s['year_active']} of the last {s['year_days']}", True),
        row("Streak", f"{days(cur_len)} now · {days(long_len)} best", True),
        row("On GitHub", since(s["created"], s["today"]), True),
    ]
    for i, runs in enumerate(rows):
        if runs:
            g.text(312, 50 + i * 22, runs, cls="mono rise", attrs=f' style="animation-delay:{i * 0.05:.2f}s"')
    return g.render(f"Shivam Kumar, Full-Stack Developer at CypherSOL Fintech, learning and building with AI. "
                    f"{s['year_total']} contributions in the last year.")


def now_next(s, t):
    g = Svg(t, 170)
    for c, (title, sub, items) in enumerate((("Now", "what I'm doing", NOW),
                                             ("Ambition", "where I'm heading", AMBITION))):
        x = 24 + c * 408
        color = t["accent"] if c == 0 else t["key"]
        if c == 0:
            g.add(f'<circle class="pulse" cx="{x + 6}" cy="37" r="5" fill="{t["live"]}"/>')
        else:
            g.add(f'<circle cx="{x + 6}" cy="37" r="5.5" fill="none" stroke="{color}" stroke-width="1.5"/>'
                  f'<circle cx="{x + 6}" cy="37" r="2" fill="{color}"/>')
        g.text(x + 20, 42, [(title, "fg", 15, 600), (f"   {sub}", "muted", 12, 400)])
        for i, item in enumerate(items):
            y = 82 + i * 30
            g.add(f'<path d="M{x + 3} {y - 4}l4.5 4-4.5 4" fill="none" stroke="{color}" stroke-width="1.6" '
                  f'stroke-linecap="round" stroke-linejoin="round"/>')
            g.text(x + 20, y + 5, item, 14, "fg", cls="rise", attrs=f' style="animation-delay:{(c * 3 + i) * 0.06:.2f}s"')
    g.add(f'<path d="M420.5 28V146" stroke="{t["grid"]}"/>')
    return g.render("Now: " + "; ".join(NOW) + ". Ambition: " + "; ".join(AMBITION) + ".")


def journey(s, t):
    """Where I am in AI: what I've built with, what I'm learning, what's next."""
    g = Svg(t, 380)
    g.title(24, 38, "My AI learning path", "From shipping LLM features to understanding and building AI systems end to end")
    col_w = (W - 48) / 3
    track_y = 82
    marks = [col_w * i + 24 + 12 for i in range(3)]
    # the path: done up to "learning now", then still ahead
    g.add(f'<path d="M{marks[0]:.1f} {track_y}H{W - 24}" stroke="{t["grid"]}" stroke-width="4" stroke-linecap="round"/>')
    g.add(f'<path class="draw" pathLength="1" d="M{marks[0]:.1f} {track_y}H{marks[1] + col_w * .45:.1f}" '
          f'stroke="{t["accent"]}" stroke-width="4" stroke-linecap="round"/>')
    for c, (stage, status, items) in enumerate(JOURNEY):
        x = 24 + c * col_w
        cx = marks[c]
        if c == 0:      # done: filled with a check
            g.add(f'<circle cx="{cx:.1f}" cy="{track_y}" r="10" fill="{t["accent"]}"/>'
                  f'<path d="M{cx - 4.5:.1f} {track_y}l3 3 6-6" fill="none" stroke="{t["bg"]}" stroke-width="2" '
                  f'stroke-linecap="round" stroke-linejoin="round"/>')
        elif c == 1:    # in progress: ring with a pulsing core
            g.add(f'<circle cx="{cx:.1f}" cy="{track_y}" r="10" fill="{t["bg"]}" stroke="{t["accent"]}" stroke-width="2.5"/>'
                  f'<circle class="pulse" cx="{cx:.1f}" cy="{track_y}" r="4.5" fill="{t["live"]}"/>')
        else:           # next: hollow
            g.add(f'<circle cx="{cx:.1f}" cy="{track_y}" r="10" fill="{t["bg"]}" stroke="{t["rest"]}" stroke-width="2"/>')
        g.text(x, track_y + 36, stage, 14, "fg", 600)
        g.text(x, track_y + 52, status, 11, "muted", cls="mono")
        for i, (name, terms) in enumerate(items):
            y = 160 + i * 50
            g.add(f'<g class="rise" style="animation-delay:{(c * 4 + i) * 0.05:.2f}s">')
            g.add(f'<rect x="{x:.1f}" y="{y}" width="{col_w - 12:.1f}" height="42" rx="8" fill="{t["tile"]}"/>')
            g.text(x + 12, y + 18, name, 13, "fg", 600)
            g.text(x + 12, y + 34, terms, 11, "muted", cls="mono")
            g.add("</g>")
    return g.render("My AI learning path. " + " ".join(
        f"{stage}: " + ", ".join(n for n, _ in items) + "." for stage, _, items in JOURNEY))


def toolkit(s, t):
    g = Svg(t, 342)
    g.title(24, 38, "AI toolkit", "The assistants, models and libraries I work with")
    tw, th, gap = (W - 48 - 4 * 12) / 5, 82, 12
    for r, (label, tools) in enumerate(TOOLKIT):
        y0 = 74 + r * (th + 40)
        g.text(24, y0 + 4, label, 11, "muted", cls="mono")
        for i, (spec, name) in enumerate(tools):
            x, y = 24 + i * (tw + gap), y0 + 14
            g.add(f'<g class="rise" style="animation-delay:{(r * 5 + i) * 0.04:.2f}s">')
            g.add(f'<rect x="{x:.1f}" y="{y}" width="{tw:.1f}" height="{th}" rx="8" fill="{t["tile"]}"/>')
            g.icon(spec, x + tw / 2 - 14, y + 14, 28, t["fg"])
            g.text(x + tw / 2, y + 66, name, 12, "fg", 500, anchor="middle")
            g.add("</g>")
    g.text(24, 74 + 2 * (th + 40) + 2, [("also  ", "muted", 11, 400), (TOOLKIT_MORE, "fg", 11, 400)], cls="mono")
    return g.render("AI toolkit: " + ", ".join(n for _, tools in TOOLKIT for _, n in tools) + ", " + TOOLKIT_MORE + ".")


def ai(s, t):
    g = Svg(t, 366)
    g.title(24, 38, "Building with AI", "LLMs, embeddings and speech in things I've built")
    tw, th, gap = (W - 48 - 24) / 3, 130, 12

    def chips(x, y, items, max_w):
        x0 = x
        for item in items:
            w = len(item) * 11 * 0.6 + 10
            if x > x0 and x + w > x0 + max_w:
                x, y = x0, y + 24
            g.add(f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="18" rx="9" fill="none" stroke="{t["border"]}"/>')
            g.text(x + 5, y + 13, item, 11, "muted", cls="mono")
            x += w + 6

    for i, (name, where, what, tools) in enumerate(AI_BUILDS):
        x, y = 24 + (i % 3) * (tw + gap), 70 + (i // 3) * (th + gap)
        g.add(f'<g class="rise" style="animation-delay:{i * 0.06:.2f}s">')
        g.add(f'<rect x="{x:.1f}" y="{y}" width="{tw:.1f}" height="{th}" rx="8" fill="{t["tile"]}"/>')
        g.text(x + 16, y + 28, name, 14, "fg", 600)
        g.text(x + 16, y + 46, where, 11, "key", cls="mono")
        for j, line in enumerate(wrap(what, 36)[:2]):
            g.text(x + 16, y + 70 + j * 16, line, 12)
        chips(x + 16, y + 98, tools, tw - 32)
        g.add("</g>")

    x, y = 24 + 2 * (tw + gap), 70 + th + gap
    g.add(f'<g class="rise" style="animation-delay:.3s">')
    g.add(f'<rect x="{x:.1f}" y="{y}" width="{tw:.1f}" height="{th}" rx="8" fill="{t["tile"]}"/>')
    g.text(x + 16, y + 28, "AI concepts I've shipped", 14, "fg", 600)
    chips(x + 16, y + 44, SHIPPED_CONCEPTS, tw - 32)
    g.add("</g>")
    return g.render("Building with AI: " + "; ".join(f"{n} ({', '.join(tl)})" for n, _, _, tl in AI_BUILDS) + ".")


def skyline(s, t):
    """The last year's calendar in 3D: one tower per day, height = contributions."""
    g = Svg(t, 404)
    weeks = s["weeks"]
    g.title(24, 38, f"{s['year_total']:,} contributions in the last year",
            "Each tower is one day; taller means more contributions")
    lx = W - 24 - 5 * 15 - 34
    g.text(lx - 8, 38, "Less", 11, anchor="end")
    for lvl in range(5):
        g.add(f'<rect x="{lx + lvl * 15}" y="28" width="11" height="11" rx="2" fill="{t["levels"][lvl]}" '
              f'stroke="{t["cell_edge"]}"/>')
    g.text(lx + 5 * 15 + 4, 38, "More", 11)

    ux, uy, vx, vy, f, hmax = 12.0, 2.8, -6.0, 6.4, 0.8, 112   # a week along u, a weekday along v
    peak = max(d["count"] for w in weeks for d in w) or 1
    ox = (W - (len(weeks) * ux - 7 * vx)) / 2 - 7 * vx
    oy = 72 + hmax
    cells = sorted(((c * uy + ((d["date"].weekday() + 1) % 7) * vy, c, (d["date"].weekday() + 1) % 7, d)
                    for c, w in enumerate(weeks) for d in w), key=lambda x: (x[0], x[1]))

    def poly(pts, fill):
        return f'<path d="M{"L".join(f"{x:.1f} {y:.1f}" for x, y in pts)}Z" fill="{fill}"/>'

    for _, c, r, d in cells:
        px, py = ox + c * ux + r * vx, oy + c * uy + r * vy
        h = max(3, d["count"] / peak * hmax) if d["count"] else 0
        color = t["levels"][d["level"]]
        a, b = (px, py), (px + ux * f, py + uy * f)
        cc, dd = (px + ux * f + vx * f, py + uy * f + vy * f), (px + vx * f, py + vy * f)
        up = lambda p: (p[0], p[1] - h)
        faces = [poly([b, cc, up(cc), up(b)], shade(color, .62)),
                 poly([dd, cc, up(cc), up(dd)], shade(color, .8))] if h else []
        faces.append(poly([up(a), up(b), up(cc), up(dd)], color))
        g.add(f'<g class="rise" style="animation-delay:{c * 0.015:.3f}s">{"".join(faces)}</g>')

    starts = [i for i, w in enumerate(weeks) if i == 0 or w[0]["date"].month != weeks[i - 1][0]["date"].month]
    for i, col in enumerate(starts):
        if i + 1 < len(starts) and starts[i + 1] - col < 3:
            continue
        g.text(ox + col * ux + 7 * vx, oy + col * uy + 7 * vy + 16, f"{weeks[col][0]['date']:%b}", 11)
    for r, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        g.text(ox + r * vx - 14, oy + r * vy + 4, name, 11, anchor="end")

    days_ = [d for w in weeks for d in w]
    busiest = max(days_, key=lambda d: (d["count"], d["date"]))
    by_weekday = s["by_weekday"]
    (by, bm), _ = max(s["months"], key=lambda m: m[1])
    facts = [("Busiest day", f"{busiest['count']} on {busiest['date']:%a}, {fmt_day(busiest['date'])}"),
             ("Most active on", f"{WEEKDAYS[by_weekday.index(max(by_weekday))]}s"),
             ("Peak month", f"{dt.date(by, bm, 1):%B %Y}")]
    for i, (label, value) in enumerate(facts):
        g.text(24, 316 + i * 22, [(f"{label}  ", "muted", 12, 400), (value, "fg", 12, 600)])
    return g.render(f"3D contribution calendar: {s['year_total']} contributions in the last year; "
                    f"busiest day {busiest['count']} contributions.")


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
    for name, card in (("hero", hero), ("now", now_next), ("journey", journey), ("toolkit", toolkit),
                       ("ai", ai), ("overview", overview), ("skyline", skyline), ("rhythm", rhythm),
                       ("years", years)):
        for theme, t in THEMES.items():
            (OUT / f"{name}-{theme}.svg").write_text(card(s, t))
    (OUT / "stats.md").write_text(table_view(s))
    print(f"{s['year_total']} contributions in the last year, {s['total']} in total, "
          f"{s['year_active']} active days, longest streak {s['longest'][1]}")


if __name__ == "__main__":
    main()
