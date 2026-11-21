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

## Managing stocks

Run `just migrate-up` and restart the backend to allow multiple stocks with the
same ticker in a family. Give each holding a name identifying its broker or owner;
grants, purchases, sales, and imports are tracked separately for each stock.

Use **Show Archived** to **Restore** a stock or **Delete permanently**. Restoring
keeps all its records. Permanent deletion requires confirmation and removes the
stock and all its grants, vestings, purchases, sales, allocations, and import history.
Active stocks must be archived first. API clients can use
`POST /api/stocks/<stock_id>/restore` or
`DELETE /api/stocks/<stock_id>?permanent=true`; ordinary `DELETE` still archives.
Downgrading the migration requires resolving duplicate family tickers first,
including archived stocks; the downgrade never deletes holdings automatically.

## Stock prices

Run `uv sync`, copy `.env.example` to `.env`, and set `ALPHAVANTAGE_API_KEY` to your
Alpha Vantage key. The root `.env` is loaded by the Python application and is
ignored by Git. An existing environment variable takes precedence, so deployments
can provide the key directly without a file.

Stock prices use Alpha Vantage's latest available end-of-day quote, with a one-hour
cache. If a refresh fails, the last known price is shown as cached with its retrieval
time. Without a configured key or a cached quote, prices and estimated values are
unavailable; stock and grant management still work. All prices and estimates are USD.

## Stock sales

Run `just migrate-up` before using the sales feature, and restart the backend to
load the new API routes. Sales record whole shares, USD proceeds per share (up to
six decimal places), and explicit quantities from each acquisition lot (an RSU
vesting release or stock purchase). Shares must have been acquired by the
transaction date; all existing sales reduce the lot's available quantity,
including sales recorded with a later transaction date. A sale can combine RSU
and ESPP shares.

Use **Holdings & sales → Record sale** to enter a sale. The ledger supports year
filtering and deletion to correct a sale by re-recording it. Grants with recorded
sales, and purchases with recorded sales, cannot be deleted until those sales are removed. Proceeds are gross amounts;
fees, capital gains, and taxes are not computed by this feature.

## ESPP purchases

Run `just migrate-up` and restart the backend before using purchases. The migration
adds `stock_purchases` and extends sale allocations while preserving existing RSU
grants and sales. Downgrading requires deleting sales allocated to purchases first;
the downgrade removes purchase records.

Use **Acquisition timeline → Add → ESPP purchase** to record a completed purchase's
date and whole-share quantity. Enter each six-month purchase separately. Purchases
appear under **ESPP** in the timeline, **Plans & purchases**, holdings, and sale lot
selection. To correct a purchase, delete it and record it again.

Purchases use the general-purpose `StockPurchase` model and stock-scoped
`/api/stocks/<stock_id>/purchases` API (list, create, and delete). API clients can
provide a different `plan_name`; the ESPP form uses `ESPP`. Prices, rebates,
fractional shares, future purchases, and purchase tax calculations are not recorded.

## Stock export

Use **Export** at the top right of a stock's detail page to download an Excel file
with all its grants, exact vesting schedules, purchases, sales, and sale allocations.
The export includes all dates, regardless of the selected tab or sales year filter.
It contains two sheets, **Plans & vestings** and **Sales**, with metadata and linked
record keys to import into another instance. Exports now use version 2, preserving
broker grant numbers and sale provenance; version 1 files can still be imported.
See [the export format](doc/stock-export.md) for the schema.

## Stock import

Run `just migrate-up` and restart the backend before using imports or grant numbers.
Use **Import** beside **Export** to upload an app export or E*TRADE expanded
gains/losses workbook. Preview does not save anything; confirm after reviewing the
records. App exports restore all data into an empty stock with the same ticker.

For E*TRADE, enter grants (including broker grant numbers) and ESPP purchases first.
Use **Plans & purchases → Grant number** to add or correct an existing grant's number.
The preview matches RSU vestings by grant number and vest date, and ESPP purchases
by purchase date. You can resolve lots, split allocations, or skip sales before
confirming. Summary and `ESPP STC` rows are ignored entirely. Prices are USD, and
wash-sale-adjusted dates and tax figures are not used.

Known imported orders are skipped. Possible manual duplicates require review;
changed facts for a recorded order/price group cannot overwrite existing sales.
All selected records save together, and retries cannot duplicate a committed batch.
See [the import workflow and API](doc/stock-import.md) for details.
