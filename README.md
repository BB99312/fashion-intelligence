# Red Cars NY Fashion Trends

A daily fashion-intelligence report covering the global apparel, footwear, accessories,
luxury, and streetwear markets — with a focus on the United States and the style hubs of
New York, Los Angeles, and Chicago.

**Live site:** published via GitHub Pages from the [`docs/`](docs/) folder.

## Structure

- `docs/index.html` — home page: latest edition + archive
- `docs/archive.html` — full archive of past editions
- `docs/trends.html` — market-trend charts by season and location
- `docs/style.css` — shared design system (Bodoni Moda + Jost, red brand accent)
- `docs/assets/redcar.svg` — the Red Cars NY brand logo
- `docs/editions/YYYY-MM-DD.html` — one dated report per day

## Automated daily generation

`scripts/generate.py` uses Claude (with the built-in web-search tools) to research the day's
fashion landscape, write a new dated edition matching the site design, and rebuild the home page
and archive. The GitHub Actions workflow in `.github/workflows/publish.yml` runs it daily and
commits the result.

**Setup:** add an `ANTHROPIC_API_KEY` repository secret (Settings → Secrets and variables →
Actions). The workflow also runs on demand via the "Run workflow" button in the Actions tab.
Run locally with `ANTHROPIC_API_KEY=… python scripts/generate.py`.

## Daily email delivery (opt-in)

After publishing, the workflow runs `scripts/send_email.py`, which emails a branded digest of the
day's edition (headline, standfirst, executive-summary bullets, and a button to the full report).
It works over standard SMTP, so any provider works (Gmail, Outlook, SendGrid, Mailgun, Amazon SES…).

It is **opt-in** — if the secrets below are not set, the step prints a notice and skips, so the
daily run is never affected. To enable, add these repository secrets:

| Secret | Required | Notes |
|---|---|---|
| `EMAIL_TO` | yes | Recipient(s), comma-separated |
| `SMTP_HOST` | yes | e.g. `smtp.gmail.com` |
| `SMTP_USER` | yes | SMTP login |
| `SMTP_PASS` | yes | Password or app password |
| `SMTP_PORT` | no | Default `587` (STARTTLS); use `465` for SSL |
| `EMAIL_FROM` | no | Defaults to `SMTP_USER` |

**Gmail example:** turn on 2-Step Verification, create an [App Password](https://myaccount.google.com/apppasswords),
then set `SMTP_HOST=smtp.gmail.com`, `SMTP_USER=you@gmail.com`, `SMTP_PASS=<the app password>`,
`EMAIL_TO=recipient@example.com`.

## Each report covers

1. **Current season trends** — colors, silhouettes, fabrics, patterns + the collections shaping them
2. **Next season predictions** — the same four pillars, forward-looking
3. **Hyped releases & emerging designers** — most-talked-about pieces and undiscovered names
4. **Consumer behavior** — where shoppers are actually spending
5. **Streetwear** — emerging brands, collaborations, big releases

Every claim is sourced and linked; rumors are labeled; market and resale figures are directional.
