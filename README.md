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

## Each report covers

1. **Current season trends** — colors, silhouettes, fabrics, patterns + the collections shaping them
2. **Next season predictions** — the same four pillars, forward-looking
3. **Hyped releases & emerging designers** — most-talked-about pieces and undiscovered names
4. **Consumer behavior** — where shoppers are actually spending
5. **Streetwear** — emerging brands, collaborations, big releases

Every claim is sourced and linked; rumors are labeled; market and resale figures are directional.
