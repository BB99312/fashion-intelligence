#!/usr/bin/env python3
"""
Red Cars NY Fashion Trends — daily report generator.

Uses Claude (with the built-in web_search / web_fetch server tools) to research
the day's fashion landscape and write a dated HTML edition, then rebuilds the
home page and archive. Designed to run from GitHub Actions on a daily schedule.

Requires the ANTHROPIC_API_KEY environment variable.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic

# ── Config ─────────────────────────────────────────────────────────────────
MODEL = "claude-opus-4-8"          # do not downgrade without intent
MAX_TOKENS = 32000                 # streamed, so timeouts are not a concern
MAX_CONTINUATIONS = 12             # safety cap on server-tool pause_turn loops

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
EDITIONS = DOCS / "editions"

BRAND = "Red Cars NY Fashion Trends"

# Eastern time so the "today" of the report matches the US focus.
EASTERN = timezone(timedelta(hours=-4))  # EDT; fine for a daily dateline

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com" />\n'
    '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />\n'
    '  <link href="https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,6..96,400;0,6..96,700;0,6..96,900;1,6..96,400;1,6..96,700&family=Jost:ital,wght@0,300;0,400;0,500;1,400&display=swap" rel="stylesheet" />'
)

# ── Research + writing prompt ────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are the Daily Fashion Intelligence Analyst for "{BRAND}", a fashion-intelligence
website. Each day you research the most current information available and write ONE comprehensive,
well-structured report on the global apparel, footwear, accessories, luxury, and streetwear markets,
with a focus on the United States and the style hubs of New York City, Los Angeles, and Chicago.

Use the web_search and web_fetch tools aggressively to discover what is happening RIGHT NOW. Prioritize
the last 24–72 hours; clearly label anything older that you include for context. Cite a source link for
every claim, trend, collaboration, and data point. If you cannot verify something, say so rather than
guessing. Flag rumors and unconfirmed reports as such. Never invent collaborations, sales figures, or
quotes. Be explicit that resale/market figures are directional rather than exact.

Pull from outlets such as Business of Fashion, Vogue, WWD, Hypebeast, Highsnobiety, The Cut, Dazed,
Complex, Who What Wear, Coveteur, and major newswires, plus retail/resale sources (StockX, GOAT, ThredUp,
McKinsey State of Fashion, eMarketer).
"""

# The exact HTML contract. The model returns ONLY the two fenced blocks.
USER_PROMPT_TEMPLATE = """Today is {weekday}, {date_long} ({date_iso}). Research and write today's edition.

Return your answer as EXACTLY two fenced blocks and nothing else outside them:

===META===
{{"date": "{date_iso}", "title": "<a punchy 6–12 word headline for today>", "dek": "<1–2 sentence standfirst>"}}
===ENDMETA===

===BODY===
<the inner HTML of the report — see the structure and CSS contract below>
===ENDBODY===

STRUCTURE (use these exact section ids and classes — they are styled by the site's stylesheet):

<div class="report-head">
  <p class="report-date">{weekday} · {date_long}</p>
  <h2 class="report-title">…same as META title…</h2>
  <p class="report-standfirst">…same as META dek…</p>
</div>

<section class="summary">
  <span class="kicker">Executive Summary</span>
  <ul><li>…4–6 bullets, &lt;strong&gt; the lead phrase of each…</li></ul>
</section>

Then SIX sections, each:
<section class="section" id="ID">
  <div class="section-head">
    <span class="section-num">NN</span>
    <span class="section-title">TITLE</span>
    <span class="section-sub">one-line subtitle</span>
  </div>
  …content using &lt;p class="prose"&gt;, and where useful the components below…
</section>

The six sections, in order, with these ids/numbers/titles:
  01 id="current"    Current Season Trends    — break out Colors / Silhouettes / Fabrics / Patterns, and the collections shaping them
  02 id="next"       Next Season Predictions  — same four pillars, forward-looking
  03 id="releases"   Hyped Releases & Emerging Designers — most-talked-about pieces (big + small brands) + undiscovered designers making noise on social
  04 id="behavior"   Consumer Behavior        — where shoppers are actually spending (resale, value, demographics); include a stat band
  05 id="streetwear" Streetwear               — emerging brands, collaborations, big releases
  +  id="pulse"      Industry & City Pulse    — breaking moves + NYC / LA / Chicago (use section-num "+")

Available components (optional, use where they help):
  • Colors as swatches:
    <div class="swatches"><div class="swatch"><div class="swatch-chip" style="background:#HEX;"></div><span class="swatch-name">Name</span><span class="swatch-hex">#HEX</span></div>…</div>
  • Attribute rows (colors/silhouettes/fabrics/patterns):
    <div class="attrs"><div class="attr"><div class="attr-label">Colors</div><div class="attr-body">…[<a href="URL">Source</a>]</div></div>…</div>
  • Designer/brand/release cards:
    <div class="grid-2"> or <div class="grid-3"> containing
      <div class="entry"><div class="entry-head"><span class="entry-name">Name</span><span class="chip">Tag</span></div><p class="entry-meta">meta</p><p class="entry-body">…[<a>Source</a>]</p></div>
  • Stat band (for §04):
    <div class="stats"><div class="stat"><div class="stat-num">$31<span class="unit">B</span></div><div class="stat-label">…</div></div>…</div>
  • Tables: <table class="ftable"><thead><tr><th>…</th></tr></thead><tbody><tr><td class="t-name">…</td><td class="t-date">…</td><td>…</td></tr></tbody></table>
  • City columns (in §pulse): <div class="cities"><div><div class="city-name">New York</div><div class="city-body">…</div></div>…</div>

After the six sections, a Watch List panel:
<div class="watch" id="watch">
  <span class="kicker">Forward Look</span>
  <h2>Watch List — Next 1–2 Weeks</h2>
  <table class="watch-table"><thead><tr><th>Date</th><th>Type</th><th>What to track</th></tr></thead>
  <tbody><tr><td class="w-date">Mon DD</td><td class="w-type">Drop</td><td>…</td></tr>…</tbody></table>
</div>

Then a Sources list:
<div class="sources"><span class="kicker">Sources</span><ol><li><a href="URL">Publisher — Title</a></li>…</ol></div>

Rules: bold brand/product/person names on first mention with &lt;strong&gt;. Put a [<a href="URL">Source</a>] link
on every claim. Label rumors with the word "rumored" and mark resale/market figures as directional. If a section
genuinely has nothing new, write "No significant new developments" rather than padding. Output ONLY the two fenced
blocks."""

# ── HTML assembly ─────────────────────────────────────────────────────────────

def page_html(date_iso: str, title: str, body: str) -> str:
    meta_comment = json.dumps({"date": date_iso, "title": title})
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{BRAND} — {date_iso}</title>
  {FONTS}
  <link rel="stylesheet" href="../style.css" />
  <!--META {meta_comment}-->
</head>
<body>

  <header class="site-head container">
    <div class="topline">
      <span><a href="../index.html">&larr;&nbsp;&nbsp;Index</a></span>
      <span>Daily Fashion Report</span>
      <span><a href="../archive.html">Archive</a></span>
    </div>
    <div class="wordmark-block">
      <div class="brandmark">
        <img class="car-logo" src="../assets/redcar.svg" alt="Red Cars NY" />
        <h1 class="wordmark"><span class="red">Red Cars NY</span><br />Fashion Trends</h1>
      </div>
      <p class="tagline">Trends · Releases · Behavior · Streetwear</p>
      <div class="accent-rule"></div>
    </div>
    <nav class="mainnav">
      <a href="#current">Current Season</a>
      <a href="#next">Next Season</a>
      <a href="#releases">Hyped &amp; Emerging</a>
      <a href="#behavior">Consumer Behavior</a>
      <a href="#streetwear">Streetwear</a>
      <a href="../trends.html">Market Charts</a>
      <a href="#watch">Watch List</a>
    </nav>
  </header>

  <main class="container">
{body}
  </main>

  <footer class="site-foot container">
    <div class="foot-mark">{BRAND}</div>
    <div class="foot-links">
      <a href="../index.html">Index</a> · <a href="../trends.html">Market Charts</a> · <a href="../archive.html">Archive</a> · Published {date_iso}
    </div>
    <p class="foot-note">Every claim is sourced and linked. Rumors are labeled. Market and resale figures are directional.</p>
  </footer>

</body>
</html>
"""


META_RE = re.compile(r"<!--META\s+(\{.*?\})\s*-->", re.DOTALL)


def scan_editions():
    """Return a list of {date, title, filename} for every edition, newest first."""
    out = []
    for path in EDITIONS.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        m = META_RE.search(text)
        if m:
            try:
                meta = json.loads(m.group(1))
                out.append({
                    "date": meta.get("date", path.stem),
                    "title": meta.get("title", path.stem),
                    "filename": path.name,
                })
                continue
            except json.JSONDecodeError:
                pass
        out.append({"date": path.stem, "title": path.stem, "filename": path.name})
    out.sort(key=lambda e: e["date"], reverse=True)
    return out


def human_date(date_iso: str) -> str:
    try:
        d = datetime.strptime(date_iso, "%Y-%m-%d")
        return d.strftime("%b %-d, %Y")
    except ValueError:
        return date_iso


def archive_items_html(editions, href_prefix=""):
    rows = []
    for e in editions:
        rows.append(
            f'        <li class="archive-item">\n'
            f'          <span class="archive-date">{human_date(e["date"])}</span>\n'
            f'          <span class="archive-headline"><a href="{href_prefix}editions/{e["filename"]}">{e["title"]}</a></span>\n'
            f'        </li>'
        )
    return "\n".join(rows)


def rebuild_index(editions, latest, dek):
    latest_link = f'editions/{latest["filename"]}'
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{BRAND} — Daily Report</title>
  {FONTS}
  <link rel="stylesheet" href="style.css" />
</head>
<body>

  <header class="site-head container">
    <div class="topline">
      <span>Daily Fashion Report</span>
      <span>Est. 2026</span>
      <span><a href="archive.html">Archive</a></span>
    </div>
    <div class="wordmark-block">
      <div class="brandmark">
        <img class="car-logo" src="assets/redcar.svg" alt="Red Cars NY" />
        <h1 class="wordmark"><span class="red">Red Cars NY</span><br />Fashion Trends</h1>
      </div>
      <p class="tagline">Trends · Releases · Behavior · Streetwear</p>
      <div class="accent-rule"></div>
    </div>
    <nav class="mainnav">
      <a href="{latest_link}#current">Current Season</a>
      <a href="{latest_link}#next">Next Season</a>
      <a href="{latest_link}#releases">Hyped &amp; Emerging</a>
      <a href="{latest_link}#behavior">Consumer Behavior</a>
      <a href="{latest_link}#streetwear">Streetwear</a>
      <a href="trends.html">Market Charts</a>
    </nav>
  </header>

  <main class="container">

    <section class="hero">
      <img class="hero-car" src="assets/redcar.svg" alt="Red Cars NY" />
      <span class="kicker hero-kicker">Latest Edition · {human_date(latest["date"])}</span>
      <h2 class="hero-title"><a href="{latest_link}">{latest["title"]}</a></h2>
      <p class="hero-dek">{dek}</p>
      <div class="hero-covers">
        <span class="tag">Current Season Trends</span>
        <span class="tag">Next Season Predictions</span>
        <span class="tag">Hyped Releases &amp; Emerging Designers</span>
        <span class="tag">Consumer Behavior</span>
        <span class="tag">Streetwear</span>
      </div>
      <div class="btn-wrap">
        <a class="btn" href="{latest_link}">Read the Report</a>
        &nbsp;&nbsp;
        <a class="btn" href="trends.html" style="background:transparent;color:var(--ink);">View Market Charts</a>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <span class="section-num">&mdash;</span>
        <span class="section-title">The Archive</span>
        <span class="section-sub">Every edition, newest first</span>
      </div>
      <ul class="archive-list">
{archive_items_html(editions)}
      </ul>
      <p style="text-align:center; margin-top:2rem;">
        <a class="kicker" href="archive.html" style="text-decoration:underline; text-underline-offset:4px;">View Full Archive</a>
      </p>
    </section>

    <section class="section" style="border-bottom:none;">
      <div class="section-head">
        <span class="section-num">&plus;</span>
        <span class="section-title">About</span>
      </div>
      <p class="about">
        <strong>{BRAND}</strong> is a daily report on the global apparel, footwear, accessories, luxury,
        and streetwear markets, with a focus on the United States and the style hubs of New York, Los Angeles,
        and Chicago. Each edition tracks the current season's trends (colors, silhouettes, fabrics, patterns),
        next-season predictions, the most-hyped releases and emerging designers, consumer-spending behavior, and
        streetwear — plus <a href="trends.html">market-trend charts</a> by season and location. Every claim is
        sourced and linked; rumors are labeled; market figures are directional. Updated each day.
      </p>
    </section>

  </main>

  <footer class="site-foot container">
    <div class="foot-mark">{BRAND}</div>
    <div class="foot-links">
      <a href="archive.html">Archive</a> · <a href="trends.html">Market Charts</a> · Updated Daily
    </div>
    <p class="foot-note">Every claim is sourced and linked. Rumors are labeled. Market and resale figures are directional.</p>
  </footer>

</body>
</html>
"""
    (DOCS / "index.html").write_text(html, encoding="utf-8")


def rebuild_archive(editions):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Archive — {BRAND}</title>
  {FONTS}
  <link rel="stylesheet" href="style.css" />
</head>
<body>

  <header class="site-head container">
    <div class="topline">
      <span><a href="index.html">&larr;&nbsp;&nbsp;Latest Edition</a></span>
      <span>Daily Fashion Report</span>
      <span>Archive</span>
    </div>
    <div class="wordmark-block">
      <div class="brandmark">
        <img class="car-logo" src="assets/redcar.svg" alt="Red Cars NY" />
        <h1 class="wordmark"><span class="red">Red Cars NY</span><br />Fashion Trends</h1>
      </div>
      <p class="tagline">Trends · Releases · Behavior · Streetwear</p>
      <div class="accent-rule"></div>
    </div>
  </header>

  <main class="container">
    <div class="page-head">
      <span class="kicker">Every Edition</span>
      <h1>The Archive</h1>
    </div>
    <section class="section" style="border-bottom:none; padding-top:0;">
      <ul class="archive-list">
{archive_items_html(editions)}
      </ul>
    </section>
  </main>

  <footer class="site-foot container">
    <div class="foot-mark">{BRAND}</div>
    <div class="foot-links">
      <a href="index.html">Latest Edition</a> · <a href="trends.html">Market Charts</a> · Updated Daily
    </div>
    <p class="foot-note">Every claim is sourced and linked. Rumors are labeled. Market and resale figures are directional.</p>
  </footer>

</body>
</html>
"""
    (DOCS / "archive.html").write_text(html, encoding="utf-8")


# ── Claude research run ───────────────────────────────────────────────────────

def run_research(client, user_prompt: str) -> str:
    """Run the message loop with server-side web tools, returning final text."""
    tools = [
        {"type": "web_search_20260209", "name": "web_search"},
        {"type": "web_fetch_20260209", "name": "web_fetch"},
    ]
    messages = [{"role": "user", "content": user_prompt}]

    for _ in range(MAX_CONTINUATIONS):
        with client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            tools=tools,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()

        # Server tools paused the turn; re-send to let the server resume.
        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        break

    return "".join(b.text for b in response.content if b.type == "text").strip()


def extract_block(name: str, text: str) -> str:
    m = re.search(rf"==={name}===\s*(.*?)\s*===END{name}===", text, re.DOTALL)
    if not m:
        raise ValueError(f"Model output missing the ==={name}=== block.")
    return m.group(1).strip()


def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Error: ANTHROPIC_API_KEY is not set.")

    now = datetime.now(EASTERN)
    date_iso = now.strftime("%Y-%m-%d")
    out_path = EDITIONS / f"{date_iso}.html"
    if out_path.exists():
        print(f"Edition for {date_iso} already exists — nothing to do.")
        return

    user_prompt = USER_PROMPT_TEMPLATE.format(
        weekday=now.strftime("%A"),
        date_long=now.strftime("%B %-d, %Y"),
        date_iso=date_iso,
    )

    print(f"Researching and writing edition for {date_iso} with {MODEL}…")
    client = anthropic.Anthropic()
    raw = run_research(client, user_prompt)

    meta = json.loads(extract_block("META", raw))
    body = extract_block("BODY", raw)
    title = meta["title"]
    dek = meta.get("dek", "")

    EDITIONS.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page_html(date_iso, title, body), encoding="utf-8")
    print(f"Wrote {out_path.relative_to(ROOT)}")

    editions = scan_editions()
    latest = editions[0]
    rebuild_index(editions, latest, dek)
    rebuild_archive(editions)
    print(f"Rebuilt index.html and archive.html ({len(editions)} editions).")


if __name__ == "__main__":
    main()
