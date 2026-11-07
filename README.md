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
record keys to support a future import into another instance. Import is not yet
available. See [the version 1 export format](doc/stock-export.md) for the schema.
