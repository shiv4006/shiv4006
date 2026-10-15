#!/usr/bin/env python3
"""Generates the SVGs in assets/ that make this profile README look like my
portfolio, https://shivam-k.vercel.app: the same grayscale palette, JetBrains
Mono, terminal windows and typing effects.

    python3 -m pip install fonttools
    python3 scripts/build.py

The content lives in the CONTENT block below. Edit it, rebuild, commit assets/.
Fonts and icons are downloaded once into scripts/.cache/. Each SVG embeds only
the glyphs it uses, so the font renders for every visitor.
"""

import base64
import io
import random
import re
import textwrap
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = Path(__file__).resolve().parent / ".cache"

FONT_URL = "https://raw.githubusercontent.com/JetBrains/JetBrainsMono/v2.304/fonts/ttf/JetBrainsMono-{}.ttf"
ICON_URLS = {
    "si": "https://cdn.jsdelivr.net/npm/simple-icons@16.30.0/icons/{}.svg",
    "fa": "https://cdn.jsdelivr.net/npm/@fortawesome/fontawesome-free@6.5.2/svgs/{}.svg",
}

# ------------------------------------------------------------------ CONTENT

TAGLINES = [
    "fintech & forensic platforms",
    "AML fraud-detection engines",
    "AI assistants with SSE streaming",
    "fast, reliable systems",
]

# The editor pane in the hero, token by token: (text, token class).
DEVELOPER_TS = [
    [("// developer.ts", "com")],
    [("const", "key"), (" ", ""), ("developer", "fn"), (" = {", "punc")],
    [("  ", ""), ("name", "prop"), (": ", "punc"), ("'Shivam Kumar'", "str"), (",", "punc")],
    [("  ", ""), ("role", "prop"), (": ", "punc"), ("'Full-Stack Developer'", "str"), (",", "punc")],
    [("  ", ""), ("company", "prop"), (": ", "punc"), ("'CypherSOL Fintech'", "str"), (",", "punc")],
    [("  ", ""), ("stack", "prop"), (": [", "punc"), ("'React'", "str"), (", ", "punc"), ("'Node'", "str"),
     (", ", "punc"), ("'TypeScript'", "str"), (", ", "punc"), ("'Python'", "str"), ("],", "punc")],
    [("  ", ""), ("focus", "prop"), (": ", "punc"), ("'financial-intelligence systems'", "str"), (",", "punc")],
    [("  ", ""), ("solved", "prop"), (": ", "punc"), ("1400", "num"), (", ", "punc"), ("// DSA problems", "com")],
    [("  ", ""), ("build", "fn"), (": (", "punc"), ("idea", "prop"), (") => ", "punc"),
     ("'scalable solution'", "str"), (",", "punc")],
    [("}", "punc")],
]

# The interactive shell in the hero: ("cmd", text) lines are typed after a "$ ".
SHELL = [
    ("dim", "Welcome. This is an interactive shell."),
    ("cmd", "whoami"),
    ("out", "Shivam Kumar — Full-Stack Developer"),
    ("out", "@ CypherSOL Fintech."),
    ("cmd", "ls"),
    ("dirs", "about  experience  projects  skills"),
    ("dirs", "achievements  coding-profiles  education"),
    ("dirs", "certifications  contact  ~resume.pdf"),
    ("cmd", "sudo hire-me"),
    ("dim", "[sudo] password for recruiter: ********"),
    ("hire", "✓ access granted. → send the offer"),
]

EXPERIENCE = [
    {
        "role": "Full Stack Developer",
        "company": "CypherSOL Fintech India Pvt. Ltd. · India",
        "duration": "Sep 2025 – Present",
        "points": [
            "Core contributor to 6 fintech & forensic products: fraud detection, statement forensics, GST",
            "Co-led the Django → Core migration (Next.js, NestJS, PostgreSQL, Redis) with zero data loss",
            "Built AML forensics (layering, circular transactions, mule scoring): 30%+ fewer duplicate merges",
            "Shipped an in-app AI assistant with SSE streaming; made React + Electron dashboards 40% faster",
            "Led 20+ production builds across 6 desktop apps",
        ],
        "tech": ["React", "Electron", "Next.js", "NestJS", "PostgreSQL"],
    },
    {
        "role": "Full Stack Developer Intern",
        "company": "Bytical Solutions Pvt. Ltd. · Gurugram, India",
        "duration": "Mar 2025 – Aug 2025",
        "points": [
            "Led development of an AI-powered avatar presentation platform",
            "Integrated Azure OpenAI and Azure Speech SDK for conversational Q&A and avatar-synced narration",
            "Managed a team of 7–10 developers; CI/CD cut deployment time by 40%",
        ],
        "tech": ["React", "FastAPI", "MongoDB", "Azure Speech SDK", "Azure OpenAI"],
    },
    {
        "role": "Summer Intern",
        "company": "Bureau of Indian Standards (BIS) · New Delhi, India",
        "duration": "May 2024 – June 2024",
        "points": [
            "Researched printer technologies and helped draft the official pre-standardization report",
        ],
        "tech": ["Research & Documentation", "Technical Writing"],
    },
]

PROJECTS = [
    {
        "name": "Fintraqq — Personal Finance Platform",
        "blurb": "Production-grade personal-finance platform on the T3 stack: end-to-end type safety, "
                 "atomic money math, hierarchical budgets, recurring cron jobs and CSV/Excel/PDF exports. "
                 "80+ features, live and used daily.",
        "tech": ["Next.js 15", "tRPC v11", "Prisma", "PostgreSQL", "NextAuth v5", "Tailwind CSS v4",
                 "Vitest", "GitHub Actions"],
        "demo": True, "code": False,
    },
    {
        "name": "AlgoSphere",
        "blurb": "DSA practice platform with 425+ curated problems, a real-time Monaco editor and Judge0 "
                 "code execution through a FastAPI microservice.",
        "tech": ["React", "Node.js", "Express.js", "MongoDB", "FastAPI", "Judge0 API"],
        "demo": True, "code": True,
    },
    {
        "name": "PizzaHub — MERN Ordering Platform",
        "blurb": "The full commerce flow (auth, cart, checkout, order tracking) with TOTP two-factor auth, "
                 "Cloudinary uploads and a Redux cart that composes tax, delivery and promo discounts.",
        "tech": ["React 19", "Redux Toolkit", "Express 5", "MongoDB", "JWT", "Cloudinary"],
        "demo": False, "code": True,
    },
    {
        "name": "Mutual Transfer",
        "blurb": "Digitalizes mutual-transfer requests for Bihar government teachers, with JWT auth, "
                 "advanced filtering and a responsive UI. Cuts search time by 70%.",
        "tech": ["React", "Node.js", "Express.js", "MongoDB", "Tailwind CSS", "JWT"],
        "demo": True, "code": True,
    },
]

SKILLS = [
    ("</>", "Languages", ["C++", "JavaScript", "TypeScript", "Python"]),
    ("O(n)", "Core CS", ["Data Structures & Algorithms", "OOPs", "DBMS", "Operating Systems",
                         "Computer Networks"]),
    ("{ }", "Frontend", ["React.js", "Next.js", "Redux Toolkit", "Tailwind CSS", "Electron", "HTML/CSS"]),
    ("[ ]", "Backend", ["Node.js", "Express.js", "NestJS", "FastAPI", "REST APIs", "SSE", "JWT / OAuth2"]),
    ("::", "Databases", ["MongoDB", "MySQL", "PostgreSQL", "Redis", "Prisma", "SQLite"]),
    ("~$", "Tools & Cloud", ["Git", "GitHub Actions (CI/CD)", "Docker", "Kubernetes", "Vercel", "GCP",
                             "Azure (Blob, Cosmos, OpenAI, Speech SDK)", "Keygen Licensing", "Postman"]),
]

ACHIEVEMENTS = [
    "GATE CSE 2025 — Qualified",
    "Knight badge on LeetCode (top ~3% globally); 1400+ problems solved",
    "LeetCode Biweekly #148 — Rank 451 · Biweekly #145 — Rank 594",
    "GFG Weekly Contest #134 — Rank 25 · CodeChef Starters #129 Div 2 — Rank 84",
    "AIR 809 in CodeKaze’24 (Coding Ninjas)",
    "8th rank — Zero-One coding competition, MCE Motihari",
]

PROFILES = [
    ("LeetCode", ("si", "leetcode"), "shiv40", "2057 · Knight"),
    ("CodeChef", ("si", "codechef"), "shiv75", "1916 · 4★"),
    ("Codeforces", ("si", "codeforces"), "shiv40", "1369 · Pupil"),
    ("HackerRank", ("si", "hackerrank"), "shiv_19", "Gold Badge"),
    ("GeeksforGeeks", ("si", "geeksforgeeks"), "shivamkum5qj0", ""),
    ("Code360", ("si", "codingninjas"), "nShiv", ""),
]

CONTACTS = [
    (("fa", "solid/envelope"), "email", "shivamkumar404090@gmail.com", "↗"),
    (("fa", "brands/linkedin"), "linkedin", "in/shivam-kumar-434437239", "↗"),
    (("fa", "brands/github"), "github", "github.com/shiv4006", "↗"),
    (("fa", "solid/file-pdf"), "resume", "Shivam_Kumar_Resume.pdf", "↓"),
]

BUTTONS = [("portfolio", True), ("resume", False), ("linkedin", False), ("leetcode", False),
           ("contact", False)]

# ------------------------------------------------------------------ DESIGN TOKENS (from the site's index.css)

BG, BG_SOFT, PANEL, PANEL_2 = "#0a0a0a", "#101010", "#141414", "#1a1a1a"
LINE, LINE_SOFT = "#2a2a2a", "#1f1f1f"
MUTED, DIM, TEXT, BRIGHT, PROMPT = "#6b6b6b", "#8a8a8a", "#d4d4d4", "#f5f5f5", "#9a9a9a"
TOKENS = {"key": ("#f5f5f5", "medium"), "fn": ("#e0e0e0", "regular"), "str": ("#b0b0b0", "regular"),
          "num": ("#cfcfcf", "regular"), "prop": ("#d4d4d4", "regular"), "punc": ("#6b6b6b", "regular"),
          "com": ("#545454", "italic"), "": ("#d4d4d4", "regular")}

VARIANTS = {"regular": ("Regular", 400, "normal"), "medium": ("Medium", 500, "normal"),
            "bold": ("Bold", 700, "normal"), "italic": ("Italic", 400, "italic")}
CW = 0.6  # JetBrains Mono advance width, in em
W = 1040  # every card shares this width so they line up in the README
X = 40    # left gutter inside a card
GLITCH = "!<>-_\\/[]{}=+*^?#"

CSS = (
    "text{font-family:'JBM',ui-monospace,'SF Mono',Menlo,Consolas,monospace;white-space:pre}"
    ".in{animation:in .5s ease-out both}"
    ".op{animation:op .25s ease-out both}"
    ".blink{animation:blink 1.06s steps(1) infinite}"
    "@keyframes in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}"
    "@keyframes op{from{opacity:0}to{opacity:1}}"
    "@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}"
    "@media (prefers-reduced-motion:reduce){.in,.op,.blink{animation:none}}"
)


def fetch(url, name):
    path = CACHE / name
    if not path.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as resp:
            path.write_bytes(resp.read())
    return path


def font_face(variant, chars):
    name, weight, style = VARIANTS[variant]
    font = TTFont(fetch(FONT_URL.format(name), f"JetBrainsMono-{name}.ttf"))
    opts = subset.Options()
    opts.layout_features = ["*"]  # keep the code ligatures (=>, //) the site shows
    opts.hinting = False
    opts.flavor = "woff"
    subsetter = subset.Subsetter(opts)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff"
    font.save(buf)
    data = base64.b64encode(buf.getvalue()).decode()
    return (f"@font-face{{font-family:'JBM';font-weight:{weight};font-style:{style};"
            f"src:url(data:font/woff;base64,{data}) format('woff')}}")


def icon_shape(source, name):
    """(width, height, path) of a Simple Icons / Font Awesome icon."""
    svg = fetch(ICON_URLS[source].format(name), f"{source}-{name.replace('/', '-')}.svg").read_text()
    vb = re.search(r'viewBox="([^"]+)"', svg).group(1).split()
    d = re.search(r'\sd="([^"]+)"', svg).group(1)
    if not re.fullmatch(r"[MmZzLlHhVvCcSsQqTtAaEe0-9.,\s+-]+", d):
        raise ValueError(f"unexpected path data in {source}/{name}")
    return float(vb[2]), float(vb[3]), d


def wrap(text, chars):
    return textwrap.wrap(text, chars, break_on_hyphens=False) or [""]


def n(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


class Svg:
    def __init__(self, width=W, fill=None):
        self.w, self.fill = width, fill
        self.parts, self.defs = [], []
        self.chars = {v: set() for v in VARIANTS}
        self.count = 0

    def uid(self, prefix):
        self.count += 1
        return f"{prefix}{self.count}"

    def add(self, markup):
        self.parts.append(markup)

    @contextmanager
    def group(self, cls=None, delay=None, attrs=""):
        if cls:
            attrs += f' class="{cls}"'
        if delay is not None:
            attrs += f' style="animation-delay:{delay:.2f}s"'
        self.add(f"<g{attrs}>")
        yield
        self.add("</g>")

    def text(self, x, y, runs, size=14, color=TEXT, variant="regular", anchor="start", attrs=""):
        """runs: a string, or (text, color[, variant]) tuples drawn one after another."""
        if isinstance(runs, str):
            runs = [(runs, color)]
        spans = []
        for run in runs:
            t, c, v = run[0], run[1], run[2] if len(run) > 2 else variant
            self.chars[v].update(t)
            _, weight, style = VARIANTS[v]
            spans.append(f'<tspan fill="{c}" font-weight="{weight}" font-style="{style}">{escape(t)}</tspan>')
        if anchor != "start":
            attrs += f' text-anchor="{anchor}"'
        self.add(f'<text xml:space="preserve" x="{n(x)}" y="{n(y)}" font-size="{n(size)}"{attrs}>{"".join(spans)}</text>')

    def rect(self, x, y, w, h, fill="none", stroke=None, rx=0, attrs=""):
        if stroke:
            attrs += f' stroke="{stroke}"'
        self.add(f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(rx)}" fill="{fill}"{attrs}/>')

    def hline(self, x1, x2, y, color=LINE):
        self.add(f'<path d="M{n(x1)} {n(y)}H{n(x2)}" stroke="{color}"/>')

    def icon(self, spec, x, y, size, color):
        w, h, d = icon_shape(*spec)
        k = size / max(w, h)
        dx, dy = x + (size - w * k) / 2, y + (size - h * k) / 2
        self.add(f'<path transform="translate({n(dx)} {n(dy)}) scale({k:.5f})" fill="{color}" d="{d}"/>')

    def cursor(self, x, y, size, cls="blink", attrs="", children=""):
        """The site's .cursor: a 0.6ch x 1.05em block sitting 0.15em below the baseline."""
        self.add(f'<rect class="{cls}" x="{n(x + 2)}" y="{n(y - 0.9 * size)}" width="{n(0.36 * size)}" '
                 f'height="{n(1.05 * size)}" fill="{BRIGHT}"{attrs}>{children}</rect>')

    def window(self, x, y, w, h, title=None):
        """A .term-window, optionally with a .term-titlebar. Returns the y where content starts."""
        self.rect(x + .5, y + .5, w - 1, h - 1, PANEL, LINE, 6)
        if title is None:
            return y
        r, bx, by, bw = 5, x + 1, y + 1, w - 2
        self.add(f'<path d="M{n(bx)} {n(by + 35)}V{n(by + r)}Q{n(bx)} {n(by)} {n(bx + r)} {n(by)}'
                 f'H{n(bx + bw - r)}Q{n(bx + bw)} {n(by)} {n(bx + bw)} {n(by + r)}V{n(by + 35)}Z" fill="{PANEL_2}"/>')
        self.hline(x + 1, x + w - 1, y + 36.5)
        for i in range(3):
            self.add(f'<circle cx="{n(x + 19.5 + i * 19)}" cy="{n(y + 18.5)}" r="5" fill="#3a3a3a" stroke="#4a4a4a"/>')
        self.text(x + 79, y + 22.5, title, 12, MUTED)
        return y + 37

    def chips(self, x, y, items, max_w, size=12):
        """Bordered tech tags (text-xs px-2 py-0.5 border rounded) that wrap. Returns the bottom y."""
        cx, cy = x, y
        for item in items:
            w = len(item) * size * CW + 16
            if cx > x and cx + w > x + max_w:
                cx, cy = x, cy + 28
            self.rect(cx + .5, cy + .5, w - 1, 19, stroke=LINE, rx=4)
            self.text(cx + 8, cy + 14, item, size, DIM)
            cx += w + 8
        return cy + 20

    def typed(self, x, y, runs, size, start, step=0.06, cursor_until=None):
        """Types the text out from `start`. SMIL with the full text as the static value, so a
        renderer that skips animation still shows everything."""
        count = sum(len(r[0]) for r in runs)
        cw = size * CW
        dur = start + step * count
        times = ";".join(["0"] + [f"{(start + step * i) / dur:.4f}" for i in range(1, count + 1)])
        timing = f'keyTimes="{times}" dur="{dur:.3f}s" calcMode="discrete" fill="freeze"'
        widths = ";".join(f"{i * cw + 2 if i else 0:.1f}" for i in range(count + 1))
        cid = self.uid("clip")
        self.defs.append(f'<clipPath id="{cid}"><rect x="{n(x - 2)}" y="{n(y - size * 1.1)}" '
                         f'width="{n(count * cw + 4)}" height="{n(size * 1.5)}">'
                         f'<animate attributeName="width" values="{widths}" {timing}/></rect></clipPath>')
        self.add(f'<g clip-path="url(#{cid})">')
        self.text(x, y, runs, size)
        self.add("</g>")
        if cursor_until is not None:
            xs = ";".join(f"{x + i * cw + 2:.1f}" for i in range(count + 1))
            self.cursor(x + count * cw, y, size, cls="", children=(
                f'<animate attributeName="x" values="{xs}" {timing}/>'
                f'<set attributeName="visibility" to="hidden" begin="{cursor_until:.2f}s" fill="freeze"/>'))
        return dur

    def typeloop(self, x, y, phrases, size, color, start, type_step=0.055, hold=1.8, del_step=0.03, gap=0.35):
        """The site's TypeLoop: types each phrase, holds, deletes, moves on, forever."""
        cw = size * CW
        events, t = [], 0.0
        for p, phrase in enumerate(phrases):
            events += [(t + type_step * i, p, i) for i in range(1, len(phrase) + 1)]
            t += type_step * len(phrase) + hold
            events += [(t + del_step * (len(phrase) - i), p, i) for i in range(len(phrase) - 1, -1, -1)]
            t += del_step * len(phrase) + gap
        total = t

        def anim(attr, points, to_value):
            values = ";".join(f"{to_value(i):.1f}" for _, i in points)
            times = ";".join(f"{tm / total:.4f}" for tm, _ in points)
            return (f'<animate attributeName="{attr}" values="{values}" keyTimes="{times}" dur="{total:.3f}s" '
                    f'begin="{start:.2f}s" repeatCount="indefinite" calcMode="discrete"/>')

        for p, phrase in enumerate(phrases):
            points = [(0.0, 0)] + [(tm, i) for tm, q, i in events if q == p] + [(total, 0)]
            cid = self.uid("clip")
            static = len(phrase) * cw + 4 if p == 0 else 0
            self.defs.append(f'<clipPath id="{cid}"><rect x="{n(x - 2)}" y="{n(y - size * 1.1)}" '
                             f'width="{n(static)}" height="{n(size * 1.5)}">'
                             f'{anim("width", points, lambda i: i * cw + 2 if i else 0)}</rect></clipPath>')
            self.add(f'<g clip-path="url(#{cid})">')
            self.text(x, y, phrase, size, color)
            self.add("</g>")
        points = [(0.0, 0)] + [(tm, i) for tm, _, i in events] + [(total, 0)]
        self.cursor(x + len(phrases[0]) * cw, y, size, children=anim("x", points, lambda i: x + i * cw + 2))

    def scramble(self, x, y, text, size, color, variant, start, dur=0.6, frames=12):
        """The site's ScrambleText: random glyphs that resolve left to right."""
        rnd = random.Random(text)
        step = dur / frames
        for k in range(frames):
            shown = len(text) * k // frames
            frame = "".join(c if i < shown or c == " " else rnd.choice(GLITCH) for i, c in enumerate(text))
            self.add('<g opacity="0">')
            self.text(x, y, [(frame, color, variant)], size)
            self.add(f'<set attributeName="opacity" to="1" begin="{start + k * step:.3f}s" dur="{step:.3f}s"/></g>')
        self.add("<g>")
        self.text(x, y, [(text, color, variant)], size)
        self.add(f'<set attributeName="opacity" to="0" begin="0s" dur="{start + dur:.3f}s"/></g>')

    def save(self, name, height):
        faces = "".join(font_face(v, cs) for v, cs in self.chars.items() if cs)
        card = ""
        if self.fill:
            card = (f'<rect x=".5" y=".5" width="{n(self.w - 1)}" height="{n(height - 1)}" rx="10" '
                    f'fill="{self.fill}" stroke="{LINE_SOFT}"/>')
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{n(self.w)}" height="{n(height)}" '
               f'viewBox="0 0 {n(self.w)} {n(height)}" xml:space="preserve">'
               f'<style>{faces}{CSS}</style><defs>{"".join(self.defs)}</defs>{card}{"".join(self.parts)}</svg>')
        ASSETS.mkdir(exist_ok=True)
        (ASSETS / name).write_text(svg)
        print(f"assets/{name}  {len(svg) // 1024} KB")


def section(tag, num, title, fill):
    """A card that opens like a site section: .section-tag, then an h2.prompt."""
    s = Svg(fill=fill)
    s.text(X, 52, [(f"~/{tag}".upper(), MUTED), (" · ", LINE), (num, MUTED)], 12.8, attrs=' letter-spacing="1.92"')
    s.text(X, 96, [("> ", PROMPT, "bold"), (title, BRIGHT, "bold")], 30)
    return s, 136


# ------------------------------------------------------------------ CARDS

def hero():
    H = 640
    s = Svg()
    # backdrop: base, drifting grid faded by a radial mask, a soft beam, scanlines (.term-grid-animated etc.)
    grid, mask, fade, beam, scan, clip = (s.uid(p) for p in ("grid", "mask", "fade", "beam", "scan", "clip"))
    s.defs += [
        f'<clipPath id="{clip}"><rect width="{W}" height="{H}" rx="10"/></clipPath>',
        f'<pattern id="{grid}" width="34" height="34" patternUnits="userSpaceOnUse">'
        f'<path d="M34 .5H.5V34" fill="none" stroke="{LINE_SOFT}"/>'
        f'<animateTransform attributeName="patternTransform" type="translate" from="0 0" to="34 34" '
        f'dur="24s" repeatCount="indefinite"/></pattern>',
        f'<radialGradient id="{fade}" cx=".5" cy=".38" r="1" '
        f'gradientTransform="translate(.5 .38) scale(.85 .75) translate(-.5 -.38)">'
        f'<stop offset=".25" stop-color="#fff"/><stop offset=".78" stop-color="#000"/></radialGradient>',
        f'<mask id="{mask}"><rect width="{W}" height="{H}" fill="url(#{fade})"/></mask>',
        f'<radialGradient id="{beam}" cx="{W * .3}" cy="{H * .2}" r="600" gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="#fff" stop-opacity=".045"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        f'</radialGradient>',
        f'<pattern id="{scan}" width="3" height="3" patternUnits="userSpaceOnUse">'
        f'<rect width="3" height="1" fill="#fff" fill-opacity=".015"/></pattern>',
    ]
    s.add(f'<g clip-path="url(#{clip})"><rect width="{W}" height="{H}" fill="{BG}"/>'
          f'<rect width="{W}" height="{H}" fill="url(#{grid})" mask="url(#{mask})" opacity=".7"/>'
          f'<rect width="{W}" height="{H}" fill="url(#{beam})"/><rect width="{W}" height="{H}" fill="url(#{scan})"/></g>'
          f'<rect x=".5" y=".5" width="{W - 1}" height="{H - 1}" rx="10" fill="none" stroke="{LINE_SOFT}"/>')

    # $ whoami / Shivam Kumar / tagline
    s.text(X, 64, [("$ ", MUTED)], 16)
    s.typed(X + 2 * 16 * CW, 64, [("whoami", DIM)], 16, start=0.3, step=0.07, cursor_until=0.95)
    s.scramble(X, 132, "Shivam Kumar", 48, BRIGHT, "bold", start=0.95)
    lead = "Full-Stack Developer — I build "
    with s.group("op", 1.55):
        s.text(X, 174, [("Full-Stack Developer — ", MUTED), ("I build ", TEXT)], 18)
        s.typeloop(X + len(lead) * 18 * CW, 174, TAGLINES, 18, BRIGHT, start=1.65)

    # dual pane: editor + interactive shell
    top, ph, ew = 212, 360, 532
    tx, tw = X + ew + 20, W - 2 * X - ew - 20
    with s.group("in", 1.8):
        s.window(X, top, ew, ph)
        s.add(f'<path d="M{X + 1} {top + 37}V{top + 6}Q{X + 1} {top + 1} {X + 6} {top + 1}'
              f'H{X + ew - 6}Q{X + ew - 1} {top + 1} {X + ew - 1} {top + 6}V{top + 37}Z" fill="{PANEL_2}"/>')
        s.hline(X + 1, X + ew - 1, top + 37.5)
        tab, cw12 = 12.8, 12.8 * CW
        w1 = 14 + 2 * cw12 + 8 + 12 * cw12 + 8 + 6 + 14
        s.add(f'<path d="M{X + 1} {top + 38}V{top + 6}Q{X + 1} {top + 1} {X + 6} {top + 1}'
              f'H{n(X + 1 + w1)}V{top + 38}Z" fill="{PANEL}"/>')
        s.add(f'<path d="M{n(X + 1 + w1 + .5)} {top + 1}V{top + 37}M{n(X + 1 + w1 + 120.5)} {top + 1}V{top + 37}" stroke="{LINE}"/>')
        s.text(X + 15, top + 24, [("TS", MUTED), (" ", MUTED), ("developer.ts", BRIGHT)], tab)
        s.add(f'<circle cx="{n(X + 1 + w1 - 17)}" cy="{top + 19.5}" r="3" fill="{DIM}"/>')
        s.text(X + w1 + 15, top + 24, [("MD", MUTED), (" ", MUTED), ("readme.md", MUTED)], tab)
    for i, line in enumerate(DEVELOPER_TS):
        y = top + 37 + 20 + 16 + i * 23.8
        with s.group("op", 2.0 + i * 0.06):
            s.text(X + 20 + 2.5 * 14 * CW, y, f"{i + 1}", 14, "#3a3a3a", anchor="end")
            s.text(X + 20 + 2.5 * 14 * CW + 20, y,
                   [(t, TOKENS[k][0], TOKENS[k][1]) for t, k in line], 14)

    with s.group("in", 1.9):
        s.window(tx, top, tw, ph, "shivam@portfolio: ~")
    y, t = top + 37 + 20 + 15, 2.3
    for kind, line in SHELL:
        if kind == "cmd":
            t += 0.25
            with s.group("op", t):
                s.text(tx + 20, y, [("$ ", MUTED)], 14)
            t = s.typed(tx + 20 + 2 * 14 * CW, y, [(line, BRIGHT)], 14, start=t) + 0.2
        else:
            with s.group("op", t):
                if kind == "dim":
                    s.text(tx + 32, y, line, 14, DIM)
                elif kind == "dirs":
                    runs = [(w[1:], DIM) if w.startswith("~") else (w, BRIGHT) for w in re.split(r"(\s+)", line)]
                    s.text(tx + 32, y, runs, 14)
                elif kind == "hire":
                    head, link = line.split("→")
                    s.text(tx + 32, y, [(head, TEXT), ("→" + link, BRIGHT)], 14)
                    lx = tx + 32 + len(head) * 14 * CW
                    s.hline(lx, lx + len("→" + link) * 14 * CW, y + 3.5, MUTED)
                else:
                    s.text(tx + 32, y, line, 14, TEXT)
            t += 0.12 if kind == "dirs" else 0.3
        y += 24
    with s.group("op", t + 0.2):
        s.text(tx + 20, y, [("$ ", MUTED)], 14)
        s.cursor(tx + 20 + 2 * 14 * CW, y, 14)

    with s.group("op", 2.4):
        s.text(W / 2, 612, "↓ scroll to explore", 12, MUTED, anchor="middle", attrs=' letter-spacing="1.2"')
    s.save("hero.svg", H)


def button(label, primary):
    """The hero's ./view-work style buttons (px-5 py-2.5 border rounded)."""
    text = f"./{label}"
    w, h = len(text) * 16 * CW + 40, 44
    s = Svg(w)
    s.rect(.5, .5, w - 1, h - 1, PANEL_2 if primary else BG, LINE, 4)
    s.text(w / 2, 27.5, text, 16, BRIGHT if primary else DIM, anchor="middle")
    s.save(f"btn-{label}.svg", h)


def experience(num, fill):
    s, y = section("experience", num, "experience", fill)
    rail = X + 8
    cx = rail + 32
    cw = W - X - cx
    chars = int((cw - 48) // (14 * CW))
    top, rail_at = y, len(s.parts)
    for exp in EXPERIENCE:
        lines = []
        for point in exp["points"]:
            wrapped = wrap(point, chars - 2)
            lines += [("- ", wrapped[0])] + [("  ", rest) for rest in wrapped[1:]]
        body = y + 101 + (len(lines) - 1) * 22.75
        chips_y = body + 22
        h = chips_y + 20 + 24 - y
        s.window(cx, y, cw, h)
        s.add(f'<circle cx="{rail + .5}" cy="{y + 30}" r="6" fill="{PANEL_2}" stroke="{DIM}"/>')
        s.text(cx + 24, y + 42, exp["role"], 18, BRIGHT, "bold")
        s.text(cx + cw - 24, y + 40, exp["duration"], 12, MUTED, anchor="end")
        s.text(cx + 24, y + 70, exp["company"], 14, DIM)
        for i, (bullet, line) in enumerate(lines):
            s.text(cx + 24, y + 101 + i * 22.75, [(bullet, MUTED), (line, TEXT)], 14)
        s.chips(cx + 24, chips_y, exp["tech"], cw - 140)
        s.text(cx + cw - 24, chips_y + 15, "more →", 14, MUTED, anchor="end")
        y += h + 24
    s.parts.insert(rail_at, f'<path d="M{rail + .5} {top}V{y - 24}" stroke="{LINE}"/>')  # under the nodes
    s.save("experience.svg", y - 24 + 48)


def projects(num, fill):
    s, y = section("projects", num, "projects", fill)
    cw = W - 2 * X
    chars = int((cw - 48) // (14 * CW))
    for p in PROJECTS:
        lines = wrap(p["blurb"], chars)
        body = y + 74 + (len(lines) - 1) * 22.75
        probe = Svg()
        chips_bottom = probe.chips(0, 0, p["tech"], cw - 48)
        chips_y = body + 22
        divider = chips_y + chips_bottom + 16
        h = divider + 16 + 20 + 24 - y
        s.window(X, y, cw, h)
        s.text(X + 24, y + 44, [("> ", MUTED, "bold"), (p["name"], BRIGHT, "bold")], 20)
        s.text(X + cw - 24, y + 42, "details →", 14, MUTED, anchor="end")
        for i, line in enumerate(lines):
            s.text(X + 24, y + 74 + i * 22.75, line, 14, TEXT)
        s.chips(X + 24, chips_y, p["tech"], cw - 48)
        s.hline(X + 1, X + cw - 1, divider + .5)
        links = []
        if p["demo"]:
            links.append([("↗", MUTED), (" live demo", DIM)])
        if p["code"]:
            links.append([("</>", MUTED), (" source", DIM)])
        lx = X + 24
        for runs in links:
            s.text(lx, divider + 16 + 15, runs, 14)
            lx += sum(len(r[0]) for r in runs) * 14 * CW + 16
        y += h + 20
    s.save("projects.svg", y - 20 + 48)


def skills(num, fill):
    s, y = section("skills", num, "skills", fill)
    cols, gap = 3, 20
    cw = (W - 2 * X - gap * (cols - 1)) / cols
    chars = int((cw - 40) // (14 * CW))
    for row in range(0, len(SKILLS), cols):
        cards = []
        for glyph, title, items in SKILLS[row:row + cols]:
            lines = []
            for item in items:
                wrapped = wrap(item, chars - 2)
                lines += [("- ", wrapped[0])] + [("  ", rest) for rest in wrapped[1:]]
            cards.append((glyph, title, lines))
        h = max(20 + 24 + 16 + len(lines) * 26 - 6 + 20 for _, _, lines in cards)
        for c, (glyph, title, lines) in enumerate(cards):
            x = X + c * (cw + gap)
            s.window(x, y, cw, h)
            s.text(x + 20, y + 37, [(glyph, MUTED, "bold"), (" " + title, BRIGHT, "bold")], 16)
            for i, (bullet, line) in enumerate(lines):
                s.text(x + 20, y + 75 + i * 26, [(bullet, MUTED), (line, TEXT)], 14)
        y += h + gap
    s.save("skills.svg", y - gap + 48)


def achievements(num, fill):
    s, y = section("achievements", num, "achievements", fill)
    h = 37 + 24 + len(ACHIEVEMENTS) * 30 - 10 + 24
    s.window(X, y, W - 2 * X, h, "achievements.log")
    for i, item in enumerate(ACHIEVEMENTS):
        s.text(X + 24, y + 37 + 24 + 15 + i * 30, [(f"{i + 1:02d}", MUTED), ("  ", MUTED), (item, TEXT)], 14)
    s.save("achievements.svg", y + h + 48)


def coding_profiles(num, fill):
    s, y = section("coding-profiles", num, "coding-profiles", fill)
    cols, gap, h = 3, 16, 84
    cw = (W - 2 * X - gap * (cols - 1)) / cols
    for i, (name, icon, user, rating) in enumerate(PROFILES):
        x, cy = X + (i % cols) * (cw + gap), y + (i // cols) * (h + gap)
        s.window(x, cy, cw, h)
        s.icon(icon, x + 16, cy + h / 2 - 12, 24, DIM)
        tx = x + 16 + 24 + 16
        lines = [([(name, BRIGHT, "bold"), (" ↗", MUTED)], 14), ([(f"@{user}", DIM)], 12)]
        if rating:
            lines.append(([(rating, MUTED)], 12))
        ty = cy + h / 2 - (len(lines) * 17) / 2 + 13
        for runs, size in lines:
            s.text(tx, ty, runs, size)
            ty += 17
    rows = -(-len(PROFILES) // cols)
    s.save("coding-profiles.svg", y + rows * h + (rows - 1) * gap + 48)


def github(num, fill):
    s, _ = section("github", num, "github", fill)
    s.text(X, 136, [("$ ", MUTED), ("gh stats --live", DIM)], 14)
    s.save("github.svg", 164)


def contact(num, fill):
    s, _ = section("contact", num, "contact", fill)
    s.text(X, 130, [("$ ", MUTED), ("Open to full-stack roles and interesting problems. Reach out —", DIM)], 14)
    y, rh = 170, 52
    h = 37 + rh * len(CONTACTS)
    s.window(X, y, W - 2 * X, h, "contact.sh")
    for i, (icon, label, value, mark) in enumerate(CONTACTS):
        ry = y + 37 + i * rh
        if i:
            s.hline(X + 1, W - X - 1, ry + .5)
        s.icon(icon, X + 20, ry + 16, 20, DIM)
        s.text(X + 20 + 20 + 16, ry + 31, label, 14, MUTED)
        s.text(X + 20 + 20 + 16 + 80 + 16, ry + 31, value, 14, TEXT)
        s.text(W - X - 20, ry + 31, mark, 14, MUTED, anchor="end")
    foot = y + h + 52
    note = "generated with python + svg, from the same design — © 2026 shivam kumar"
    nx = (W - len(note) * 12 * CW - 8) / 2
    s.text(nx, foot, note, 12, MUTED)
    s.cursor(nx + len(note) * 12 * CW + 2, foot, 12)
    s.save("contact.svg", foot + 40)


def main():
    hero()
    for label, primary in BUTTONS:
        button(label, primary)
    cards = [experience, projects, skills, achievements, coding_profiles, github, contact]
    for i, card in enumerate(cards):
        card(f"{i + 1:02d}", BG if i % 2 == 0 else BG_SOFT)


if __name__ == "__main__":
    main()
