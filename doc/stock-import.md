# Stock workbook import

Run the `d8f41a2c6b90` migration (`just migrate-up`) and restart the backend. This
adds optional grant numbers, broker sale provenance, and durable import receipts.
Existing records and creation-token retry hashes are preserved. Downgrading removes
the new metadata and receipts, while retaining grants, purchases, and sales.

## UI workflow

Open a stock and choose **Import**, select an `.xlsx`, and choose **Preview import**.
The server detects an app export or an E*TRADE expanded gains/losses report. It reads
only; no records or uploaded files are persisted during preview.

App exports restore the entire file into an empty stock with the same ticker,
including the exported stock name. Versions 1 and 2 are supported. File keys map to
fresh destination IDs. Repeated fields and acquisition references must be consistent;
explicit schedules, including customized future releases, are preserved.

E*TRADE imports create sales only. Enter grants, vestings, and purchases first. Broker
grant numbers are optional in ordinary grant entry, unique per stock, and editable
from **Plans & purchases → Grant number**. Leading zeros are significant.

The broker preview automatically selects unique source lots; otherwise choose lots
and whole-share quantities. Allocations may split across existing lots. RSU and ESPP
share quantities must remain unchanged, sources must be acquired by the sale date,
and the entire selected batch must fit current availability. Check the review box
for warnings, possible duplicates, and edited or unresolved automatic matches.
Mappings do not change grant numbers or acquisition records. Skip an individual sale
to leave it out; unsupported and conflicting sales must be skipped or corrected.

## Broker columns

The importer locates one worksheet with the expanded report's required headers.
It does not depend on the worksheet name. Blank rows and `Summary` are ignored;
`ESPP STC` is ignored entirely, with no reduction in lot balances. Supported sale
types are `RS` / `Sell Restricted Stock` and `ESPP` / `Sell ESPP`.

| Field | Use |
| --- | --- |
| Symbol | Must match the current stock; mixed-symbol files are rejected. |
| Date Sold | Sale date; broker text uses US `MM/DD/YYYY`, or a native Excel date. |
| Quantity | Whole shares sold from that source lot. |
| Proceeds Per Share | USD price; up to six decimals, without conversion or averaging. |
| Total Proceeds | Cross-check; differences above $0.01 require review. |
| Order Number | Broker identifier, stored as text. |
| Grant Number + Vest Date | Exact automatic RSU source matching. |
| Purchase Date | Automatic matching to an `ESPP` purchase on that date. |
| Grant Date + Date Acquired | Cross-checks, never replacements for source-lot dates. |

Rows with the same order number, date, currency, and exact price form one sale;
quantities from the same acquisition lot are combined. Different prices remain
separate executions. Wash-sale-adjusted dates, cost basis, ordinary income, gain/loss,
FMV, purchase prices, and other tax fields never populate a sale.

## Duplicates and atomicity

Previously imported identical broker groups are skipped automatically. The stored
fingerprint describes normalized broker facts, independent of local lot IDs and
wash-sale splits. Changed facts for the same group require correction of the saved
sale or an explicit skip; they cannot overwrite it. Additional price/date groups
for a known order require review. Manually recorded sales with the same date,
quantity, price, and currency are flagged for an explicit review/import or skip.
Version 2 exports preserve provenance so the same protection works after restoration.

Confirmation reparses the original workbook, checks all decisions, and compares a
fingerprint of current stock metadata, acquisitions, and sales with the preview.
Any intervening change requires a new preview. All selected changes and an import
receipt commit in one transaction under the stock lock. Reusing the same UUID
idempotency key and request replays the receipt; changing the request with that key
returns a conflict. A failed commit leaves no partial acquisitions, sales, or receipt.

## API

- `POST /api/stocks/<stock_id>/import/preview`: multipart field `file`. Returns
  `format`, `file_digest`, `stock_revision`, `counts`, `grants`, `purchases`, `sales`,
  `lots`, `ignored`, `errors`, and `can_import`. Proposals carry file keys/source rows.
- `POST /api/stocks/<stock_id>/import`: multipart `file`, `stock_revision`, and
  JSON text `decisions`; UUID `Idempotency-Key` header. For E*TRADE, decisions are keyed
  by each preview sale's `key`, with optional boolean `skip`, boolean `reviewed`, and
  replacement `allocations` using `{vesting_id, quantity}` or `{purchase_id, quantity}`.
  Native restores require empty decisions. Returns format and imported/skipped counts;
  `201` on commit or `200` on replay. Unresolved decisions return `400` with a preview;
  stale state or conflicting retry keys return `409`.
- `PATCH /api/stocks/<stock_id>/grants/<grant_id>`: JSON `{ "grant_number": "000123" }`
  or null to clear. Only this metadata field may be changed through this endpoint.

Both upload routes use the existing `404` missing-stock and `410` archived-stock/family
rules. Only `.xlsx` is accepted, with 10 MiB upload, 100 MiB expanded archive, and
100,000-row limits. Files are read without evaluating formulas or external links;
formula cells in imported fields, malformed workbooks, broken references, and unknown
native schema versions are rejected. No broker API requests or quote lookups occur.
