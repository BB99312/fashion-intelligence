#!/usr/bin/env python3
"""
Red Cars NY Fashion Trends — daily email sender.

Emails a clean, branded digest of the latest edition (headline, standfirst,
executive-summary bullets, and a button to the full report on the live site).

Opt-in: if the required SMTP settings or recipients are missing, this script
prints a notice and exits 0 — it never fails the daily workflow.

Configuration (all via environment variables / GitHub Actions secrets):
  EMAIL_TO     Recipient(s), comma-separated.            (required)
  SMTP_HOST    SMTP server hostname, e.g. smtp.gmail.com (required)
  SMTP_USER    SMTP username / login                     (required)
  SMTP_PASS    SMTP password or app password             (required)
  SMTP_PORT    SMTP port. Default 587 (STARTTLS); use 465 for SSL.
  EMAIL_FROM   From address. Default: SMTP_USER.
  SITE_URL     Live site base URL. Default the GitHub Pages URL below.
"""

from __future__ import annotations

import os
import re
import smtplib
import sys
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EDITIONS = ROOT / "docs" / "editions"
BRAND = "Red Cars NY Fashion Trends"
ACCENT = "#c0152f"
INK = "#16130e"
BONE = "#f4f1ea"
DEFAULT_SITE = "https://bb99312.github.io/fashion-intelligence"
EASTERN = timezone(timedelta(hours=-4))

META_RE = re.compile(r"<!--META\s+(\{.*?\})\s*-->", re.DOTALL)


def strip_tags(html: str) -> str:
    text = re.sub(r"<[^>]+>", "", html)
    text = (text.replace("&amp;", "&").replace("&ldquo;", "“")
                .replace("&rdquo;", "”").replace("&mdash;", "—")
                .replace("&nbsp;", " ").replace("&plus;", "+").replace("&rarr;", "→"))
    return re.sub(r"\s+", " ", text).strip()


def pick_edition() -> Path | None:
    """Today's edition if it exists, else the most recent one."""
    today = EDITIONS / f"{datetime.now(EASTERN).strftime('%Y-%m-%d')}.html"
    if today.exists():
        return today
    files = sorted(EDITIONS.glob("20*.html"), reverse=True)
    return files[0] if files else None


def parse_edition(path: Path):
    html = path.read_text(encoding="utf-8")
    title = path.stem
    m = META_RE.search(html)
    if m:
        import json
        try:
            title = json.loads(m.group(1)).get("title", title)
        except json.JSONDecodeError:
            pass

    def grab(pattern):
        mm = re.search(pattern, html, re.DOTALL)
        return strip_tags(mm.group(1)) if mm else ""

    standfirst = grab(r'<p class="report-standfirst">(.*?)</p>')
    date_label = grab(r'<p class="report-date">(.*?)</p>')

    bullets = []
    sm = re.search(r'<section class="summary">(.*?)</section>', html, re.DOTALL)
    if sm:
        bullets = [strip_tags(li) for li in re.findall(r"<li>(.*?)</li>", sm.group(1), re.DOTALL)]
    return title, date_label, standfirst, bullets


def build_html(title, date_label, standfirst, bullets, url):
    items = "".join(
        f'<li style="margin:0 0 12px;padding:0;line-height:1.5;color:{INK};font-size:15px;">{b}</li>'
        for b in bullets
    )
    return f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:{BONE};">
  <div style="max-width:600px;margin:0 auto;background:{BONE};
              font-family:Georgia,'Times New Roman',serif;padding:32px 28px;">
    <div style="text-align:center;border-bottom:1px solid {INK};padding-bottom:18px;margin-bottom:24px;">
      <div style="font-size:13px;letter-spacing:3px;text-transform:uppercase;color:{ACCENT};font-family:Arial,sans-serif;">Red Cars NY</div>
      <div style="font-size:26px;font-weight:bold;color:{INK};margin-top:4px;">Fashion Trends</div>
      <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#6f6a62;font-family:Arial,sans-serif;margin-top:10px;">{date_label}</div>
    </div>
    <h1 style="font-size:26px;line-height:1.15;color:{INK};margin:0 0 14px;">{title}</h1>
    <p style="font-size:15px;line-height:1.6;color:#4a443b;margin:0 0 26px;">{standfirst}</p>
    <div style="font-size:12px;letter-spacing:2px;text-transform:uppercase;color:{ACCENT};font-family:Arial,sans-serif;margin:0 0 12px;">Today's Highlights</div>
    <ul style="margin:0 0 28px;padding:0 0 0 20px;">{items}</ul>
    <div style="text-align:center;margin:8px 0 28px;">
      <a href="{url}" style="display:inline-block;background:{INK};color:{BONE};
         text-decoration:none;font-family:Arial,sans-serif;font-size:13px;letter-spacing:2px;
         text-transform:uppercase;padding:14px 30px;">Read the Full Report &rarr;</a>
    </div>
    <p style="text-align:center;font-family:Arial,sans-serif;font-size:11px;color:#968f81;
              border-top:1px solid #cfc7b7;padding-top:16px;margin:0;">
      {BRAND} — sent daily. Every claim is sourced; figures are directional.<br>
      <a href="{url}" style="color:#968f81;">View in browser</a>
    </p>
  </div>
</body></html>"""


def build_text(title, date_label, standfirst, bullets, url):
    lines = [f"RED CARS NY FASHION TRENDS — {date_label}", "", title, "", standfirst,
             "", "TODAY'S HIGHLIGHTS", ""]
    lines += [f"  • {b}" for b in bullets]
    lines += ["", f"Read the full report: {url}", "",
              f"{BRAND} — sent daily. Every claim is sourced; figures are directional."]
    return "\n".join(lines)


def main():
    to = os.environ.get("EMAIL_TO", "").strip()
    host = os.environ.get("SMTP_HOST", "").strip()
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASS", "").strip()

    if not (to and host and user and password):
        print("Email not configured (need EMAIL_TO, SMTP_HOST, SMTP_USER, SMTP_PASS). Skipping.")
        return

    port = int(os.environ.get("SMTP_PORT", "587"))
    sender = os.environ.get("EMAIL_FROM", "").strip() or user
    site = os.environ.get("SITE_URL", DEFAULT_SITE).rstrip("/")
    recipients = [r.strip() for r in to.split(",") if r.strip()]

    edition = pick_edition()
    if edition is None:
        print("No edition found to send. Skipping.")
        return
    url = f"{site}/editions/{edition.name}"
    title, date_label, standfirst, bullets = parse_edition(edition)

    msg = EmailMessage()
    msg["Subject"] = f"{title} — {BRAND}"
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.set_content(build_text(title, date_label, standfirst, bullets, url))
    msg.add_alternative(build_html(title, date_label, standfirst, bullets, url), subtype="html")

    print(f"Sending '{title}' to {len(recipients)} recipient(s) via {host}:{port}…")
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as s:
                s.login(user, password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=30) as s:
                s.starttls()
                s.login(user, password)
                s.send_message(msg)
    except Exception as e:  # don't fail the workflow over a mail hiccup
        print(f"Email send failed: {e}", file=sys.stderr)
        return
    print("Email sent.")


if __name__ == "__main__":
    main()
