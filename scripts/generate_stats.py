"""
generate_stats.py
Pulls GitHub GraphQL stats and renders SVG graphics:
  stats.svg   - total contributions + weekly sparkline
  streak.svg  - current streak / longest streak
  langs.svg   - top languages by bytes
  year.svg    - 365-day contribution heatmap (ASCII ramp)
  hd-*.svg    - section heading SVGs
Run by GitHub Actions nightly. Needs GITHUB_TOKEN + GH_LOGIN env vars.
"""

import os, json, urllib.request, urllib.error, datetime, base64, math
from pathlib import Path

ROOT     = Path(__file__).resolve().parent.parent
TOKEN    = os.environ["GITHUB_TOKEN"]
LOGIN    = os.environ.get("GH_LOGIN", "lucky-panchal")
API      = "https://api.github.com/graphql"

RAMP     = " .`:-=+*cs#%@"
BG       = "#ffffff"
FG       = "#111111"
DIM      = "#888888"
ACCENT   = "#111111"
FONT_FAM = "JBM,'Courier New',monospace"
FONT_SIZE= 12.9

# ────────────────────────────────────────────────────────────────────────────
def gql(query, variables=None):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(API, data=payload, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type":  "application/json",
    })
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["data"]

def embed_font(name):
    p = ROOT / "scripts" / "fonts" / f"{name}.woff2"
    if not p.exists():
        return ""
    b64 = base64.b64encode(p.read_bytes()).decode()
    return (f"@font-face{{font-family:'JBM';"
            f"src:url('data:font/woff2;base64,{b64}') format('woff2');"
            f"font-weight:400;font-style:normal;}}")

def style_block(extra=""):
    css = embed_font("basic")
    return (f"<style>{css}{extra}"
            f"text{{font-family:{FONT_FAM};fill:{FG};}}"
            f"</style>")

# ── Date window ─────────────────────────────────────────────────────────────
today = datetime.date.today()
FROM  = (today - datetime.timedelta(days=364)).strftime("%Y-%m-%dT00:00:00Z")
TO    = today.strftime("%Y-%m-%dT23:59:59Z")

QUERY_CONTRIB = """
query($login:String!, $from:DateTime!, $to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from, to:$to){
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      contributionCalendar{
        totalContributions
        weeks{
          contributionDays{
            date
            contributionCount
          }
        }
      }
    }
    repositories(privacy:PUBLIC, first:100, orderBy:{field:UPDATED_AT,direction:DESC}){
      nodes{
        name
        languages(first:10, orderBy:{field:SIZE, direction:DESC}){
          edges{ size node{ name } }
        }
      }
    }
  }
}
"""

data    = gql(QUERY_CONTRIB, {"login": LOGIN, "from": FROM, "to": TO})
user    = data["user"]
col     = user["contributionsCollection"]
cal     = col["contributionCalendar"]
total   = cal["totalContributions"]

# flatten days
all_days = [d for w in cal["weeks"] for d in w["contributionDays"]]

# weekly buckets (Mon–Sun)
weeks = [w["contributionDays"] for w in cal["weeks"]]
weekly_totals = [sum(d["contributionCount"] for d in w) for w in weeks]

# ── streak ───────────────────────────────────────────────────────────────────
counts     = [d["contributionCount"] for d in all_days]
dates_str  = [d["date"]             for d in all_days]

cur_streak = lon_streak = tmp = 0
cur_start  = cur_end = lon_start = lon_end = None
for i, c in enumerate(counts):
    if c > 0:
        tmp += 1
        if tmp == 1:
            s = dates_str[i]
        if tmp > lon_streak:
            lon_streak = tmp
            lon_start  = s
            lon_end    = dates_str[i]
    else:
        tmp = 0

# current streak (trailing)
tmp2 = 0
for i in range(len(counts)-1, -1, -1):
    if counts[i] > 0:
        tmp2 += 1
    else:
        if tmp2 > 0:
            break
cur_streak = tmp2
if cur_streak > 0:
    cur_end   = dates_str[-1]
    cur_start = dates_str[len(dates_str)-cur_streak]

# ── languages ───────────────────────────────────────────────────────────────
lang_bytes = {}
for repo in user["repositories"]["nodes"]:
    for edge in repo["languages"]["edges"]:
        n = edge["node"]["name"]
        lang_bytes[n] = lang_bytes.get(n, 0) + edge["size"]

top_langs = sorted(lang_bytes.items(), key=lambda x: -x[1])[:6]
total_bytes = sum(b for _, b in top_langs) or 1

# ════════════════════════════════════════════════════════════════════════════
# SVG HELPERS
# ════════════════════════════════════════════════════════════════════════════
def svg_wrap(w, h, body, extra_style=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}">'
            f'{style_block(extra_style)}'
            f'<rect width="{w}" height="{h}" fill="{BG}"/>'
            f'{body}</svg>')

def label(x, y, txt, size=11, color=None, anchor="start"):
    col = color or FG
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{col}" text-anchor="{anchor}">{txt}</text>'

def hairline(x1, y1, x2, y2, color=None):
    c = color or "#e0e0e0"
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{c}" stroke-width="0.5"/>'

# ════════════════════════════════════════════════════════════════════════════
# 1. stats.svg  — total + sparkline
# ════════════════════════════════════════════════════════════════════════════
W, H = 620, 90
sparkline_x = 220
spark_w     = W - sparkline_x - 20
spark_h     = 55
spark_top   = 18

wt = weekly_totals[-52:] if len(weekly_totals) >= 52 else weekly_totals
mx = max(wt) or 1
bar_w = spark_w / max(len(wt), 1)

bars = ""
for i, v in enumerate(wt):
    bh = int((v / mx) * spark_h)
    bx = sparkline_x + i * bar_w
    by = spark_top + spark_h - bh
    bars += f'<rect x="{bx:.1f}" y="{by}" width="{bar_w-1:.1f}" height="{bh}" fill="{ACCENT}"/>'

body = (
    label(20, 38, f"{total:,}", size=32) +
    label(20, 54, "contributions · past year", size=10, color=DIM) +
    hairline(sparkline_x-10, spark_top-4, sparkline_x-10, spark_top+spark_h+4) +
    bars +
    label(sparkline_x, spark_top+spark_h+14, "weekly activity — past 52 weeks", size=9, color=DIM)
)
(ROOT / "stats.svg").write_text(svg_wrap(W, H, body), encoding="utf-8")
print("stats.svg written")

# ════════════════════════════════════════════════════════════════════════════
# 2. streak.svg
# ════════════════════════════════════════════════════════════════════════════
W, H = 620, 80
half = W // 2

def streak_block(x, num, label_txt, sub):
    return (
        f'<text x="{x+half//2}" y="36" font-size="30" text-anchor="middle" fill="{FG}">{num}</text>'
        f'<text x="{x+half//2}" y="52" font-size="10" text-anchor="middle" fill="{FG}">{label_txt}</text>'
        f'<text x="{x+half//2}" y="66" font-size="9"  text-anchor="middle" fill="{DIM}">{sub}</text>'
    )

sub_cur = f"{cur_start} – {cur_end}" if cur_start else "—"
sub_lon = f"{lon_start} – {lon_end}" if lon_start else "—"

body = (
    streak_block(0,    cur_streak, "current streak", sub_cur) +
    hairline(half, 10, half, H-10) +
    streak_block(half, lon_streak, "longest streak", sub_lon)
)
(ROOT / "streak.svg").write_text(svg_wrap(W, H, body), encoding="utf-8")
print("streak.svg written")

# ════════════════════════════════════════════════════════════════════════════
# 3. langs.svg
# ════════════════════════════════════════════════════════════════════════════
W  = 620
ROW_H = 22
H  = 16 + len(top_langs) * ROW_H + 12
BAR_X = 160
BAR_W = W - BAR_X - 20

rows_svg = ""
for i, (lang, b) in enumerate(top_langs):
    y   = 20 + i * ROW_H
    pct = b / total_bytes
    bw  = int(pct * BAR_W)
    rows_svg += (
        label(20, y+12, lang, size=11) +
        f'<rect x="{BAR_X}" y="{y}" width="{bw}" height="13" fill="{ACCENT}"/>' +
        label(BAR_X + bw + 6, y+11, f"{pct*100:.1f}%", size=9, color=DIM)
    )

(ROOT / "langs.svg").write_text(svg_wrap(W, H, rows_svg), encoding="utf-8")
print("langs.svg written")

# ════════════════════════════════════════════════════════════════════════════
# 4. year.svg  — 365 days, one char per day using RAMP
# ════════════════════════════════════════════════════════════════════════════
days = all_days[-365:]
mx   = max(d["contributionCount"] for d in days) or 1

# 7 rows × N cols grid
CELL  = 10
COLS2 = math.ceil(len(days) / 7)
W2    = COLS2 * CELL + 40
H2    = 7 * CELL + 30

cells = ""
for idx, d in enumerate(days):
    col2 = idx // 7
    row2 = idx  % 7
    x2   = 20 + col2 * CELL
    y2   = 20 + row2 * CELL
    c    = d["contributionCount"]
    ch   = RAMP[int(c / mx * (len(RAMP)-1))]
    cells += f'<text x="{x2}" y="{y2+CELL-2}" font-size="9" fill="{ACCENT}">{ch}</text>'

month_labels = ""
prev_m = None
for idx, d in enumerate(days):
    m = d["date"][5:7]
    if m != prev_m:
        col2 = idx // 7
        mx2  = 20 + col2 * CELL
        month_labels += label(mx2, H2-5, datetime.date(int(d["date"][:4]),int(m),1).strftime("%b"), size=8, color=DIM)
        prev_m = m

(ROOT / "year.svg").write_text(svg_wrap(W2, H2, cells+month_labels), encoding="utf-8")
print("year.svg written")

# ════════════════════════════════════════════════════════════════════════════
# 5. Section heading SVGs
# ════════════════════════════════════════════════════════════════════════════
def make_heading(filename, text):
    W, H = 620, 28
    rule_x = len(text) * 7.5 + 24
    body = (
        label(0, 18, text.lower(), size=12) +
        hairline(rule_x, 12, W, 12)
    )
    (ROOT / filename).write_text(svg_wrap(W, H, body), encoding="utf-8")
    print(f"{filename} written")

make_heading("hd-about.svg",     "about")
make_heading("hd-stack.svg",     "stack")
make_heading("hd-projects.svg",  "projects")
make_heading("hd-stats.svg",     "stats")
make_heading("hd-connect.svg",   "connect")

print("All SVGs generated.")
