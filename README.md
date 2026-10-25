# eftweb

This is a Web UI for the python lib easyfrenchtax.

It uses flask and bootstrap - I'm learning these 2 frameworks as I code, so expect some wild changes at this stage.


# Run

`FLASK_APP=app.py FLASK_ENV=development flask run`

## Stock prices

Run `uv sync`, copy `.env.example` to `.env`, and set `ALPHAVANTAGE_API_KEY` to your
Alpha Vantage key. The root `.env` is loaded by the Python application and is
ignored by Git. An existing environment variable takes precedence, so deployments
can provide the key directly without a file.

Stock prices use Alpha Vantage's latest available end-of-day quote, with a one-hour
cache. If a refresh fails, the last known price is shown as cached with its retrieval
time. Without a configured key or a cached quote, prices and estimated values are
unavailable; stock and grant management still work. All prices and estimates are USD.
