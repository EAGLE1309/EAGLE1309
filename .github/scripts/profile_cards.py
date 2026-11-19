#!/usr/bin/env python3
"""Pixel-art profile cards for the README: contribution graph + stats/languages/streak panel.
Runs with the standard library only, so it works on a stock GitHub Actions runner."""
import argparse, datetime as dt, json, math, os, re, sys, urllib.request

# Silkscreen glyphs (OFL), 5px caps
GLYPHS = {
    'A': '..##.|.#..#|.####|.#..#|.#..#',
    'B': '.###.|.#..#|.####|.#..#|.###.',
    'C': '..##.|.#..#|.#...|.#..#|..##.',
    'D': '.###.|.#..#|.#..#|.#..#|.###.',
    'E': '.###|.#..|.###|.#..|.###',
    'F': '.###|.#..|.###|.#..|.#..',
    'G': '..###|.#...|.#.##|.#..#|..##.',
    'H': '.#..#|.#..#|.####|.#..#|.#..#',
    'I': '.#|.#|.#|.#|.#',
    'J': '....#|....#|....#|.#..#|..##.',
    'K': '.#..#|.#.#.|.##..|.#.#.|.#..#',
    'L': '.#..|.#..|.#..|.#..|.###',
    'M': '.#...#|.##.##|.#.#.#|.#...#|.#...#',
    'N': '.#...#|.##..#|.#.#.#|.#..##|.#...#',
    'O': '..##.|.#..#|.#..#|.#..#|..##.',
    'P': '.###.|.#..#|.###.|.#...|.#...',
    'Q': '.###.|.#..#|.#..#|.#.##|..###',
    'R': '.###.|.#..#|.###.|.#.#.|.#..#',
    'S': '..###|.#...|..##.|....#|.###.',
    'T': '.###|..#.|..#.|..#.|..#.',
    'U': '.#..#|.#..#|.#..#|.#..#|..##.',
    'V': '.#...#|.#...#|..#.#.|..#.#.|...#..',
    'W': '.#...#|.#.#.#|.#.#.#|.#.#.#|..#.#.',
    'X': '.#...#|..#.#.|...#..|..#.#.|.#...#',
    'Y': '.#...#|..#.#.|...#..|...#..|...#..',
    'Z': '.###|...#|..#.|.#..|.###',
    '0': '..##.|.#..#|.#..#|.#..#|..##.',
    '1': '.##.|..#.|..#.|..#.|.###',
    '2': '.###.|....#|..##.|.#...|.####',
    '3': '.###.|....#|..##.|....#|.###.',
    '4': '.#.#.|.#.#.|.####|...#.|...#.',
    '5': '.####|.#...|.###.|....#|.###.',
    '6': '..##.|.#...|.###.|.#..#|..##.',
    '7': '.####|....#|...#.|..#..|..#..',
    '8': '..##.|.#..#|..##.|.#..#|..##.',
    '9': '..##.|.#..#|..###|....#|..##.',
    ',': '...|...|...|..#|.#.',
    '.': '..|..|..|.#|..',
    '-': '....|....|.###|....|....',
    '+': '...#..|...#..|.#####|...#..|...#..',
    ':': '..|.#|..|.#|..',
    '/': '...#|...#|..#.|.#..|.#..',
    "'": '.#|.#|..|..|..',
    '·': '..|..|.#|..|..',
    '@': '..###.|.#.#.#|.#.##.|.#....|..###.',
    '%': '.##..#|.##.#.|...#..|..#.##|.#..##',
    ' ': '...|...|...|...|...',
}


# ----------------------------------------------------------------------------- palette
SKY = ["#071030", "#0b1a48", "#102660", "#16347c", "#1d4598"]
LEVELS = [  # (highlight, base, shade)
    ("#164a3f", "#10333b", "#0a2430"),
    ("#2c813a", "#1d633c", "#164a3f"),
    ("#86bf3c", "#4f9f38", "#2c813a"),
    ("#bcd84a", "#86bf3c", "#4f9f38"),
    ("#fbf6a6", "#e6e86a", "#bcd84a"),
]
FLOWERS = ["#ff8c3a", "#56b6ff", "#f0f6ff", "#ffe680"]
FRAME = dict(out="#2e2a22", frame="#5e5444", hi="#8c7a5c", dk="#3a352b", panel="#0b1f26")
P = 2          # svg px per art px
CELL, PITCH = 6, 7


# ----------------------------------------------------------------------------- data
def fetch_html(user):
    req = urllib.request.Request(f"https://github.com/users/{user}/contributions",
                                 headers={"User-Agent": "pixel-contrib-graph"})
    h = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    tips = dict(re.findall(r'<tool-tip[^>]*\bfor="([^"]+)"[^>]*>\s*([^<]*?)\s*</tool-tip>', h))
    days = []
    for td in re.findall(r"<td\b[^>]*ContributionCalendar-day[^>]*>", h):
        d = re.search(r'data-date="([\d-]+)"', td)
        l = re.search(r'data-level="(\d)"', td)
        i = re.search(r'\bid="([^"]+)"', td)
        if not (d and l):
            continue
        m = re.match(r"(\d+)\s+contribution", tips.get(i.group(1), "") if i else "")
        days.append({"date": d.group(1), "level": int(l.group(1)), "count": int(m.group(1)) if m else 0})
    tot = re.search(r"([\d,]+)\s+contributions?\s+in the last year", re.sub(r"\s+", " ", h))
    if not days:
        raise RuntimeError("no calendar cells found")
    total = int(tot.group(1).replace(",", "")) if tot else sum(x["count"] for x in days)
    return total, days


def fetch_graphql(user, token):
    q = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar{"
         "totalContributions weeks{contributionDays{date contributionCount contributionLevel}}}}}}")
    body = json.dumps({"query": q, "variables": {"login": user}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={"Authorization": f"bearer {token}", "User-Agent": "pixel-contrib-graph"})
    cal = json.load(urllib.request.urlopen(req, timeout=30))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    lv = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
    days = [{"date": d["date"], "count": d["contributionCount"], "level": lv[d["contributionLevel"]]}
            for w in cal["weeks"] for d in w["contributionDays"]]
    return cal["totalContributions"], days


# ----------------------------------------------------------------------------- pixel canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = c

    def rect(self, x, y, w, h, c):
        for yy in range(max(0, y), min(self.h, y + h)):
            row = self.px[yy]
            for xx in range(max(0, x), min(self.w, x + w)):
                row[xx] = c

    def text(self, s, x, y, c, scale=1, shadow=None):
        if shadow:
            self.text(s, x, y + scale, shadow, scale)
        cx = x
        for ch in s.upper():
            g = GLYPHS.get(ch, GLYPHS[" "]).split("|")
            for r, row in enumerate(g):
                for k, v in enumerate(row):
                    if v == "#":
                        self.rect(cx + k * scale, y + r * scale, scale, scale, c)
            cx += (len(g[0]) + 1) * scale
        return cx - x

    def svg_paths(self):
        out, prev = [], {}
        for y in range(self.h):
            row, x, cur = self.px[y], 0, {}
            while x < self.w:
                c = row[x]
                if c is None:
                    x += 1
                    continue
                x2 = x
                while x2 < self.w and row[x2] == c:
                    x2 += 1
                key = (x, x2, c)
                if key in prev:
                    prev[key][3] += 1
                    cur[key] = prev[key]
                else:
                    r = [x, y, x2 - x, 1, c]
                    out.append(r)
                    cur[key] = r
                x = x2
            prev = cur
        by = {}
        for (x, y, w, h, c) in out:
            by.setdefault(c, []).append(f"M{x * P} {y * P}h{w * P}v{h * P}h{-w * P}z")
        return "".join(f'<path fill="{c}" d="{"".join(d)}"/>' for c, d in by.items())


def text_width(s, scale=1):
    return sum((len(GLYPHS.get(ch, GLYPHS[" "]).split("|")[0]) + 1) * scale for ch in s.upper())


def h32(*a):
    x = 2166136261
    for v in a:
        for ch in str(v):
            x = ((x ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return x / 0xFFFFFFFF


def vnoise(x, y, s=0):
    xi, yi = math.floor(x), math.floor(y)
    xf, yf = x - xi, y - yi
    u, v = xf * xf * (3 - 2 * xf), yf * yf * (3 - 2 * yf)
    a, b = h32(xi, yi, s), h32(xi + 1, yi, s)
    c, d = h32(xi, yi + 1, s), h32(xi + 1, yi + 1, s)
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v


def vine(cv, x0, x1, y, seed):
    for x in range(x0, x1):
        yy = y + round(1.2 * math.sin(x * 0.35))
        cv.set(x, yy, "#2b4428")
        r = h32(seed, x)
        if r < 0.28:
            up = -1 if h32(seed, x, 1) < 0.5 else 1
            cv.set(x, yy + up, "#3e5a30")
            cv.set(x + 1, yy + up, "#6f8a3c" if up < 0 else "#3e5a30")


# ----------------------------------------------------------------------------- render
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def render(user, total, days):
    days = sorted(days, key=lambda d: d["date"])
    first = dt.date.fromisoformat(days[0]["date"])
    start = first - dt.timedelta(days=(first.weekday() + 1) % 7)       # back to Sunday
    cols = ((dt.date.fromisoformat(days[-1]["date"]) - start).days // 7) + 1
    LEFT, TOP_SKY = 27, 3
    SKY_H = 36
    gw = cols * PITCH - 1
    W = LEFT + gw + 10
    sky_bot = TOP_SKY + SKY_H
    month_y = sky_bot + 7
    grid_y = month_y + 9
    foot_y = grid_y + 7 * PITCH + 5
    H = foot_y + 13
    cv = Canvas(W, H)

    # stone frame + dark meadow panel
    cv.rect(2, 0, W - 4, H, FRAME["out"]); cv.rect(0, 2, W, H - 4, FRAME["out"])
    cv.rect(1, 1, W - 2, H - 2, FRAME["frame"])
    cv.rect(1, 1, W - 2, 1, FRAME["hi"]); cv.rect(1, 1, 1, H - 2, FRAME["hi"])
    cv.rect(1, H - 2, W - 2, 1, FRAME["dk"]); cv.rect(W - 2, 1, 1, H - 2, FRAME["dk"])
    cv.rect(3, 3, W - 6, H - 6, FRAME["panel"])

    # --- sky band: banded night gradient with checker dither at band edges
    bands = len(SKY)
    for y in range(TOP_SKY, sky_bot):
        t = (y - TOP_SKY) / SKY_H * bands
        for x in range(3, W - 3):
            k = int(t + (0.22 if (x + y) % 2 else -0.22))
            cv.set(x, y, SKY[max(0, min(bands - 1, k))])
    # planet rising in the top-right corner
    pcx, pcy, R = W - 30, sky_bot + 64, 92
    for y in range(TOP_SKY, sky_bot):
        for x in range(3, W - 3):
            dd = math.hypot(x - pcx, y - pcy) - R
            if dd < 0:
                din = -dd
                nx, ny = (x - pcx) / R, (y - pcy) / R
                land = vnoise(nx * 9 + 3, ny * 22 + 1, 7) * 0.65 + vnoise(nx * 20, ny * 46, 8) * 0.35
                if din < 1.2:
                    c = "#f6ffe0"
                elif din < 3:
                    c = "#8fe8ff"
                elif land > 0.55:
                    c = "#a8e45a" if land > 0.68 else ("#7cce44" if land > 0.6 else "#4fae3c")
                else:
                    c = "#2f86dc" if (x * 3 + y) % 7 else "#57aef0"
                    if land < 0.35:
                        c = "#1f62c4"
                cv.set(x, y, c)
            elif dd < 1:
                cv.set(x, y, "#b8f6ff")
            elif dd < 2.5:
                cv.set(x, y, "#79dcff")
            elif dd < 4 and (x + y) % 2:
                cv.set(x, y, "#4bb4f4")
    # static stars (twinkling ones are added as animated rects)
    stars, tw = [], []
    for i in range(46):
        x = 4 + int(h32("sx", i) * (W - 8)); y = TOP_SKY + 1 + int(h32("sy", i) * (SKY_H - 4))
        if math.hypot(x - pcx, y - pcy) - R < 6:
            continue
        if x < text_width(f"{total:,} CONTRIBUTIONS", 2) + 14 and y < TOP_SKY + 30:
            continue
        c = ["#ffffff", "#fff2b8", "#cfeeff", "#6a9ae0", "#6a9ae0"][int(h32("sc", i) * 5)]
        (tw if h32("st", i) < 0.35 else stars).append((x, y, c))
    for (x, y, c) in stars:
        cv.set(x, y, c)

    # title
    title = f"{total:,} CONTRIBUTIONS"
    cv.text(title, 9, TOP_SKY + 7, "#e2a94a", scale=2, shadow="#7a4e18")
    cv.text(f"IN THE LAST YEAR · @{user}", 10, TOP_SKY + 22, "#9ad8ff")

    # horizon: lit grass edge under the planet, darker to the left
    for x in range(3, W - 3):
        lit = max(0.0, 1 - abs(x - (W - 120)) / 160)
        tip = h32("tuft", x)
        cv.set(x, sky_bot, "#bcd84a" if lit > 0.6 else ("#4f9f38" if lit > 0.25 else "#1d633c"))
        cv.set(x, sky_bot + 1, "#86bf3c" if lit > 0.6 else ("#2c813a" if lit > 0.25 else "#164a3f"))
        cv.set(x, sky_bot + 2, "#2c813a" if lit > 0.5 else "#10333b")
        if tip < 0.3:
            cv.set(x, sky_bot - 1, "#86bf3c" if lit > 0.5 else "#1d633c")
    vine(cv, 5, 70, H - 5, 1)
    vine(cv, W - 70, W - 5, H - 5, 2)

    # month + weekday labels
    lab = "#5f8f7a"
    last_lab = -9
    for c in range(cols):
        for r in range(7):
            d = start + dt.timedelta(days=c * 7 + r)
            if d.day == 1 and c - last_lab >= 4 and c < cols - 2:
                cv.text(MONTHS[d.month - 1], LEFT + c * PITCH, month_y, lab)
                last_lab = c
    for r, name in ((1, "MON"), (3, "WED"), (5, "FRI")):
        cv.text(name, 6, grid_y + r * PITCH, lab)

    # tiles
    bydate = {d["date"]: d for d in days}
    today = days[-1]["date"]
    today_xy = None
    for c in range(cols):
        for r in range(7):
            d = start + dt.timedelta(days=c * 7 + r)
            rec = bydate.get(d.isoformat())
            if rec is None:
                continue
            lvl = max(0, min(4, rec["level"]))
            hi, base, sh = LEVELS[lvl]
            x0, y0 = LEFT + c * PITCH, grid_y + r * PITCH
            cv.rect(x0 + 1, y0, CELL - 2, 1, hi)
            cv.rect(x0, y0 + 1, 1, CELL - 2, hi)
            cv.rect(x0 + 1, y0 + 1, CELL - 2, CELL - 2, base)
            cv.rect(x0 + 1, y0 + CELL - 1, CELL - 2, 1, sh)
            cv.rect(x0 + CELL - 1, y0 + 1, 1, CELL - 2, sh)
            if lvl == 3:
                cv.set(x0 + 2 + int(h32(d, "f") * 2), y0 + 2 + int(h32(d, "g") * 2), FLOWERS[int(h32(d, "c") * 4)])
            if lvl == 4:
                cv.set(x0 + 2, y0 + 2, "#fffbe0"); cv.set(x0 + 3, y0 + 3, "#fffbe0")
            if d.isoformat() == today:
                today_xy = (x0, y0)

    # legend + range
    lx = W - 10 - text_width("MORE") - 5 * PITCH - text_width("LESS") - 6
    ly = foot_y
    lx += cv.text("LESS", lx, ly + 1, lab) + 2
    for i, (hi, base, sh) in enumerate(LEVELS):
        cv.rect(lx + 1, ly, CELL - 2, 1, hi); cv.rect(lx, ly + 1, 1, CELL - 2, hi)
        cv.rect(lx + 1, ly + 1, CELL - 2, CELL - 2, base)
        cv.rect(lx + 1, ly + CELL - 1, CELL - 2, 1, sh); cv.rect(lx + CELL - 1, ly + 1, 1, CELL - 2, sh)
        lx += PITCH
    cv.text("MORE", lx + 3, ly + 1, lab)
    f0 = dt.date.fromisoformat(days[0]["date"]); f1 = dt.date.fromisoformat(days[-1]["date"])
    cv.text(f"{MONTHS[f0.month - 1]} {f0.year} - {MONTHS[f1.month - 1]} {f1.year}", LEFT, ly + 1, lab)

    # --- animated layer (CSS works in SVGs shown through <img>)
    anim = []
    for i, (x, y, c) in enumerate(tw):
        anim.append(f'<rect class="tw" style="animation-delay:-{h32("d", i) * 3:.2f}s" x="{x * P}" y="{y * P}" '
                    f'width="{P}" height="{P}" fill="{c}"/>')
    # shooting star
    ss = "".join(f'<rect x="{(-j) * P}" y="{round(-j * 0.33) * P}" width="{P}" height="{P}" fill="{c}"/>'
                 for j, c in enumerate(["#ffffff"] * 3 + ["#b8f6ff"] * 4 + ["#79dcff"] * 4 + ["#4f92e0"] * 3))
    sx0 = max(text_width(title, 2) + 30, int(W * 0.45))
    anim.append(f'<g class="ss" style="--x:{sx0 * P}px;--y:{(TOP_SKY + 4) * P}px">{ss}</g>')
    # fireflies drifting over the meadow
    for i in range(6):
        fx0 = text_width(title, 2) + 24
        fx = fx0 + int(h32("fx", i) * (W * 0.62 - fx0)); fy = sky_bot - 7 + int(h32("fy", i) * 4)
        anim.append(f'<rect class="ff f{i % 3}" style="animation-delay:-{h32("fd", i) * 6:.2f}s" x="{fx * P}" y="{fy * P}" '
                    f'width="{P}" height="{P}" fill="#fff38a"/>')
    if today_xy:
        x0, y0 = today_xy
        ring = "".join(f'<rect x="{(x0 + a) * P}" y="{(y0 + b) * P}" width="{w * P}" height="{h * P}" fill="#e2a94a"/>'
                       for (a, b, w, h) in ((0, -1, CELL, 1), (0, CELL, CELL, 1), (-1, 0, 1, CELL), (CELL, 0, 1, CELL)))
        anim.append(f'<g class="td">{ring}</g>')
    css = ("<style>"
           ".tw{animation:tw 3.2s steps(1) infinite}@keyframes tw{0%,100%{opacity:1}50%{opacity:.2}}"
           ".ss{opacity:0;animation:ss 9s steps(36) infinite}"
           "@keyframes ss{0%{opacity:1;transform:translate(var(--x),var(--y))}"
           "10%{opacity:1;transform:translate(calc(var(--x) + 144px),calc(var(--y) + 48px))}"
           "10.1%,100%{opacity:0;transform:translate(calc(var(--x) + 144px),calc(var(--y) + 48px))}}"
           ".ff{animation:fl 2.4s steps(1) infinite,f0 9s steps(18) infinite alternate}"
           ".f1{animation:fl 2.4s steps(1) infinite,f1 11s steps(22) infinite alternate}"
           ".f2{animation:fl 2.4s steps(1) infinite,f2 7s steps(14) infinite alternate}"
           "@keyframes fl{0%,100%{opacity:1}60%{opacity:.15}}"
           "@keyframes f0{to{transform:translate(36px,-8px)}}@keyframes f1{to{transform:translate(-44px,4px)}}"
           "@keyframes f2{to{transform:translate(20px,-6px)}}"
           ".td{animation:tw 1.4s steps(1) infinite}"
           "@media (prefers-reduced-motion:reduce){*{animation:none!important}.ss{opacity:0}}"
           "</style>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * P}" height="{H * P}" viewBox="0 0 {W * P} {H * P}" '
            f'shape-rendering="crispEdges"><title>{total:,} contributions in the last year</title>{css}'
            f'{cv.svg_paths()}{"".join(anim)}</svg>'), W


# ----------------------------------------------------------------------------- stats card
ICONS = {
    "star": ("#e2a94a", "...#...|..###..|#######|.#####.|..###..|.##.##.|.#...#."),
    "commit": ("#86bf3c", "...#...|..###..|.#...#.|##...##|.#...#.|..###..|...#..."),
    "pr": ("#79dcff", ".#...#.|###.###|.#...#.|.#...#.|.#..#..|.#.#...|.##...."),
    "issue": ("#ff8c3a", "..###..|.#...#.|#.....#|#..#..#|#.....#|.#...#.|..###.."),
    "repo": ("#efe4c9", "...#...|.#####.|#######|.......|#.#.#.#|#.#.#.#|#######"),
}
FLAME = ["....#....", "...##....", "...###...", "..####.#.", ".#####.#.", ".#######.", "##.####.#",
         "##..###.#", "#....#..#", "##.....##", ".##...##.", "..#####.."]
FLAME_C = {0: "#ff8c3a", 1: "#ffe680"}
LANG_FALLBACK = "#8c9caa"


def graphql(token, query, variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", data=body,
                                 headers={"Authorization": f"bearer {token}", "User-Agent": "pixel-profile-cards"})
    out = json.load(urllib.request.urlopen(req, timeout=60))
    if "errors" in out:
        raise RuntimeError(out["errors"])
    return out["data"]


def fetch_stats(user, token):
    q = """query($login:String!){user(login:$login){createdAt
      contributionsCollection{totalCommitContributions}
      pullRequests{totalCount} issues{totalCount}
      repositoriesContributedTo(first:1,contributionTypes:[COMMIT,ISSUE,PULL_REQUEST,REPOSITORY]){totalCount}
      repositories(first:100,ownerAffiliations:OWNER,isFork:false,privacy:PUBLIC){nodes{stargazerCount
        languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}}}}"""
    u = graphql(token, q, {"login": user})["user"]
    sizes, colors = {}, {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            sizes[n] = sizes.get(n, 0) + e["size"]
            colors[n] = e["node"]["color"] or LANG_FALLBACK
    tot = sum(sizes.values()) or 1
    langs = [(n, colors[n], 100 * s / tot) for n, s in sorted(sizes.items(), key=lambda kv: -kv[1])[:5]]
    # full contribution history for streaks: one aliased contributionsCollection per year
    y0, y1 = int(u["createdAt"][:4]), dt.date.today().year
    parts = [f'y{y}:contributionsCollection(from:"{y}-01-01T00:00:00Z",to:"{y}-12-31T23:59:59Z")'
             f'{{contributionCalendar{{weeks{{contributionDays{{date contributionCount}}}}}}}}' for y in range(y0, y1 + 1)]
    hist = graphql(token, "query($login:String!){user(login:$login){" + " ".join(parts) + "}}", {"login": user})["user"]
    days = {}
    for v in hist.values():
        for w in v["contributionCalendar"]["weeks"]:
            for d in w["contributionDays"]:
                days[d["date"]] = d["contributionCount"]
    return dict(stars=sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
                commits=u["contributionsCollection"]["totalCommitContributions"],
                prs=u["pullRequests"]["totalCount"], issues=u["issues"]["totalCount"],
                contributed=u["repositoriesContributedTo"]["totalCount"], langs=langs, **streaks(days))


def streaks(days):
    ds = sorted(d for d in days if d <= dt.date.today().isoformat())
    total = sum(days[d] for d in ds)
    first = next((d for d in ds if days[d] > 0), ds[0] if ds else None)
    best, best_rng, run, run_start = 0, None, 0, None
    for d in ds:
        if days[d] > 0:
            run_start = d if run == 0 else run_start
            run += 1
            if run > best:
                best, best_rng = run, (run_start, d)
        else:
            run = 0
    # current streak: today may still be empty without breaking it
    cur, cur_rng, i = 0, None, len(ds) - 1
    if i >= 0 and days[ds[i]] == 0:
        i -= 1
    end = ds[i] if i >= 0 else None
    while i >= 0 and days[ds[i]] > 0:
        cur += 1
        i -= 1
    if cur:
        cur_rng = (ds[i + 1], end)
    return dict(total_all=total, since=first, cur=cur, cur_rng=cur_rng, best=best, best_rng=best_rng)


def fmt_day(iso):
    d = dt.date.fromisoformat(iso)
    return f"{MONTHS[d.month - 1]} {d.day}"


def frame(cv, W, H):
    cv.rect(2, 0, W - 4, H, FRAME["out"]); cv.rect(0, 2, W, H - 4, FRAME["out"])
    cv.rect(1, 1, W - 2, H - 2, FRAME["frame"])
    cv.rect(1, 1, W - 2, 1, FRAME["hi"]); cv.rect(1, 1, 1, H - 2, FRAME["hi"])
    cv.rect(1, H - 2, W - 2, 1, FRAME["dk"]); cv.rect(W - 2, 1, 1, H - 2, FRAME["dk"])
    cv.rect(3, 3, W - 6, H - 6, FRAME["panel"])


def glyph_rows(cv, rows, x, y, cmap):
    for r, row in enumerate(rows):
        for k, ch in enumerate(row):
            if ch in cmap:
                cv.set(x + k, y + r, cmap[ch])


def pillar(cv, x, y0, y1):
    cv.rect(x - 2, y0, 5, 2, "#cdb993"); cv.rect(x - 2, y1 - 2, 5, 2, "#cdb993")
    cv.rect(x - 1, y0 + 2, 3, y1 - y0 - 4, "#a8936c"); cv.rect(x - 1, y0 + 2, 1, y1 - y0 - 4, "#efe4c9")


def ring(cv, cx, cy, r, c, c2):
    """Pixel circle: bright on the upper half, shaded on the lower half, two pixels thick."""
    for a in range(0, 1440):
        t = math.radians(a / 4)
        for rr in (r, r + 1):
            x, y = round(cx + rr * math.cos(t)), round(cy + rr * math.sin(t))
            cv.set(x, y, c2 if (rr == r + 1 and math.sin(t) > 0.15) else c)


def render_stats(user, s, W=407):
    TOP_H = 82
    STRIP_H = 44
    H = 6 + TOP_H + STRIP_H + 4
    cv = Canvas(W, H)
    frame(cv, W, H)
    lab, val, gold, shadow = "#a9b8a4", "#efe4c9", "#e2a94a", "#7a4e18"
    mid = W // 2
    # --- left: github stats
    cv.text("GITHUB STATS", 12, 10, gold, shadow=shadow)
    rows = [("star", "STARS EARNED", s["stars"]), ("commit", "COMMITS THIS YEAR", s["commits"]),
            ("pr", "PULL REQUESTS", s["prs"]), ("issue", "ISSUES", s["issues"]),
            ("repo", "CONTRIBUTED TO", s["contributed"])]
    for i, (ic, name, v) in enumerate(rows):
        y = 22 + i * 11
        c, g = ICONS[ic]
        glyph_rows(cv, g.split("|"), 12, y - 1, {"#": c})
        cv.text(name, 23, y, lab)
        vs = f"{v:,}"
        cv.text(vs, mid - 12 - text_width(vs), y, val)
        for x in range(23 + text_width(name) + 2, mid - 14 - text_width(vs), 2):
            cv.set(x, y + 4, "#2b4a44")
    pillar(cv, mid, 8, TOP_H + 2)
    # --- right: languages
    rx = mid + 10
    cv.text("TOP LANGUAGES", rx, 10, gold, shadow=shadow)
    bw = W - 12 - rx
    cv.rect(rx - 1, 22, bw + 2, 8, FRAME["out"])
    x = rx
    langs = s["langs"]
    for j, (n, c, pct) in enumerate(langs):
        w = round(bw * pct / 100) if j < len(langs) - 1 else rx + bw - x
        w = max(w, 1)
        cv.rect(x, 23, w, 6, c)
        x += w
    for xx in range(rx, rx + bw):            # glassy top highlight + bottom shade on the bar
        cv.set(xx, 23, blend(cv.px[23][xx], "#ffffff", 0.35))
        cv.set(xx, 28, blend(cv.px[28][xx], "#000000", 0.30))
    for j, (n, c, pct) in enumerate(langs[:5]):
        lx = rx; ly = 34 + j * 10
        cv.rect(lx, ly, 5, 5, c); cv.rect(lx, ly, 5, 1, blend(c, "#ffffff", 0.35)); cv.rect(lx, ly + 4, 5, 1, blend(c, "#000000", 0.3))
        ps = f"{pct:.1f}%"
        cv.text(n.upper(), lx + 9, ly, lab)
        cv.text(ps, rx + bw - text_width(ps), ly, val)
        for x in range(lx + 9 + text_width(n.upper()) + 2, rx + bw - text_width(ps) - 2, 2):
            cv.set(x, ly + 4, "#2b4a44")
    # --- bottom strip: streaks, on the night-meadow band
    sy = 6 + TOP_H
    for y in range(sy, sy + STRIP_H):
        t = (y - sy) / STRIP_H
        for x in range(3, W - 3):
            k = int(t * 3 + (0.2 if (x + y) % 2 else -0.2))
            cv.set(x, y, ["#071030", "#0b1a48", "#102660"][max(0, min(2, k))])
    for x in range(3, W - 3):
        cv.set(x, sy, "#5e5444"); cv.set(x, sy + 1, "#3a352b")
    third = (W - 6) // 3
    cx1 = 3 + third // 2; cx3 = W - 3 - third // 2
    for i in range(18):
        x = 6 + int(h32("ssx", i) * (W - 12)); y = sy + 4 + int(h32("ssy", i) * (STRIP_H - 8))
        if all(abs(x - c) > 56 for c in (cx1, mid, cx3)) or y < sy + 7:
            cv.set(x, y, ["#ffffff", "#cfeeff", "#6a9ae0"][int(h32("ssc", i) * 3)])
    # left: total
    tv = f"{s['total_all']:,}"
    cv.text(tv, cx1 - text_width(tv, 2) // 2, sy + 9, val, scale=2, shadow="#05081a")
    cv.text("TOTAL CONTRIBUTIONS", cx1 - text_width("TOTAL CONTRIBUTIONS") // 2, sy + 23, gold)
    if s.get("since"):
        d = dt.date.fromisoformat(s["since"]); ss = f"SINCE {MONTHS[d.month - 1]} {d.year}"
        cv.text(ss, cx1 - text_width(ss) // 2, sy + 32, "#6a9ae0")
    # middle: current streak with a pixel flame
    cvs = str(s["cur"])
    nw = text_width(cvs, 2)
    fx = mid - (nw + 12) // 2
    glyph_rows(cv, FLAME, fx, sy + 6, {"#": "#ff8c3a"})
    glyph_rows(cv, ["....", ".##.", "####", ".##."], fx + 2, sy + 12, {"#": "#ffe680"})
    cv.text(cvs, fx + 12, sy + 9, val, scale=2, shadow="#05081a")
    cv.text("DAY STREAK", mid - text_width("DAY STREAK") // 2, sy + 23, gold)
    if s.get("cur_rng"):
        a, b = s["cur_rng"]; rs = f"{fmt_day(a)} - {fmt_day(b)}"
        cv.text(rs, mid - text_width(rs) // 2, sy + 32, "#6a9ae0")
    # right: longest
    bv = str(s["best"])
    cv.text(bv, cx3 - text_width(bv, 2) // 2, sy + 9, val, scale=2, shadow="#05081a")
    cv.text("LONGEST STREAK", cx3 - text_width("LONGEST STREAK") // 2, sy + 23, gold)
    if s.get("best_rng"):
        a, b = s["best_rng"]; rs = f"{fmt_day(a)} - {fmt_day(b)}"
        cv.text(rs, cx3 - text_width(rs) // 2, sy + 32, "#6a9ae0")
    vine(cv, 5, 60, H - 4, 3)
    vine(cv, W - 60, W - 5, H - 4, 4)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W * P}" height="{H * P}" viewBox="0 0 {W * P} {H * P}" '
            f'shape-rendering="crispEdges"><title>GitHub stats for @{user}</title>{cv.svg_paths()}</svg>')


def blend(a, b, t):
    if a is None:
        return b
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * (1 - t) + y * t):02x}" for x, y in zip(ca, cb))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--calendar-json", help="render the graph from a saved {total, days} file")
    ap.add_argument("--stats-json", help="render the stats card from a saved stats file")
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    token = os.environ.get("GITHUB_TOKEN", "")
    if a.calendar_json:
        data = json.load(open(a.calendar_json)); total, days = data["total"], data["days"]
    else:
        try:
            total, days = fetch_html(a.user)
        except Exception as e:
            print("html fetch failed, trying GraphQL:", e, file=sys.stderr)
            total, days = fetch_graphql(a.user, token)
    svg, W = render(a.user, total, days)
    open(os.path.join(a.out_dir, "contrib-graph.svg"), "w").write(svg)
    print(f"contrib-graph.svg: {total} contributions, {len(days)} days")
    stats = json.load(open(a.stats_json)) if a.stats_json else fetch_stats(a.user, token)
    open(os.path.join(a.out_dir, "stats.svg"), "w").write(render_stats(a.user, stats, W))
    print(f"stats.svg: {stats['stars']} stars, streak {stats['cur']}, best {stats['best']}")


if __name__ == "__main__":
    main()
