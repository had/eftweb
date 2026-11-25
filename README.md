# eftweb

This is a Web UI for the python lib easyfrenchtax.

It uses flask and bootstrap - I'm learning these 2 frameworks as I code, so expect some wild changes at this stage.


# Run

`FLASK_APP=app.py FLASK_ENV=development flask run`

## Tax estimation parameters

At startup, the backend loads [app/tax_parameters.toml](app/tax_parameters.toml)
into easyfrenchtax's shared parameter dictionary. Each section is a **filing
year**, not an income year: `[2026]` applies to the return filed in 2026 for income
earned in 2025.

Add a section with all five fields to support another year, or edit an existing
section to override its library parameters. Unlisted years retain the library's
values. Set `TAX_PARAMETERS_FILE` in `.env` or the environment to use a different
TOML file; this replaces the bundled file. Restart all backend workers after
editing it. Invalid or missing files prevent startup rather than silently using
other rates.

## Stock prices

Stock prices use Alpha Vantage's latest available end-of-day quote, with a one-hour
cache. If a refresh fails, the last known price is shown as cached with its retrieval
time. Without a configured key or a cached quote, prices and estimated values are
unavailable; stock and grant management still work. All prices and estimates are USD.

Copy `.env.example` to `.env`, and set `ALPHAVANTAGE_API_KEY` to your
Alpha Vantage key. An existing environment variable takes precedence, so deployments
can provide the key directly without a file.

