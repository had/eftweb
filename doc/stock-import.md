# Stock workbook import

Run the migrations through `ef2a91c7d430` (`just migrate-up`) and restart the backend.
The latest migration adds approval date and taxpayer metadata to grants, six-decimal
USD acquisition FMV to vestings/purchases, optional USD selling fees, and the stock-tax
statement/helper tables. Existing monetary additions become zero; unknown approval
dates and taxpayer assignments remain unset. Holdings remain usable, but incomplete
records cannot produce an accepted tax preparation.

## UI workflow

Open a stock and choose **Import**, select an `.xlsx`, and choose **Preview import**.
The server detects an app export or an E*TRADE expanded gains/losses report. It reads
only; no records or uploaded files are persisted during preview.

App exports restore the entire file into an empty stock with the same ticker,
including the exported stock name. Schema version 3 carries approval date, taxpayer, unit acquisition FMV and selling fees. Historical-format compatibility is not guaranteed. File keys map to
fresh destination IDs. Repeated fields and acquisition references must be consistent;
explicit schedules, including customized future releases, are preserved.

E*TRADE imports create sales only. Enter grants, vestings, and purchases first. Broker
grant numbers are optional in ordinary grant entry, unique per stock, and editable
from **Plans & purchases → Edit**. Leading zeros are significant.

The broker preview automatically selects unique source lots; otherwise choose lots
and whole-share quantities. Allocations may split across existing lots. RSU and ESPP
share quantities must remain unchanged, sources must be acquired by the sale date,
and the entire selected batch must fit current availability. Check the review box
for warnings, possible duplicates, and edited or unresolved automatic matches.
Mappings preserve grant numbers and acquisition quantities. A selected new sale also saves acquisition FMV atomically on its matched lots. A different existing nonzero FMV is a conflict, not an enrichment proposal. Skip an individual sale
to leave it out; unsupported and conflicting sales must be skipped or corrected.

To clear a stock's recorded sales, open **Holdings & sales → Activity ledger →
Delete all sales**. Confirmation shows the stock and total count; this removes sales
across all years, regardless of the ledger filter, in one transaction. Grants,
purchases and their acquisition FMVs remain, and their sold shares become available
again. Other stock holdings, including holdings with the same ticker, and saved tax
statements/helpers are retained. A subsequent import can record the sales again.

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
| Vest Date FMV | RSU unit acquisition FMV in USD, up to six decimals. |
| Purchase Date Fair Mkt. Value | ESPP unit acquisition FMV in USD, up to six decimals; not discounted purchase price. |
| Grant Date + Date Acquired | Cross-checks, never replacements for source-lot dates. |

Rows with the same order number, date, currency, and exact price form one sale;
quantities from the same acquisition lot are combined. Different prices remain
separate executions. Preserve each source lot’s FMV before grouping; different lots
are never averaged. Missing FMV is entered per allocation in preview before importing,
or the sale can be skipped. Repeated FMVs for one lot must agree. Existing nonzero
FMV is reused and cannot be overwritten by a new sale.

Enter one optional total USD fee per broker order, default zero. It is apportioned by
gross proceeds across every execution in the uploaded workbook before skips or duplicate
detection, conserving cents deterministically. Skipped/duplicate executions retain
their share. The saved execution fee is apportioned across its acquisition lines in
the 2074 calculation. Do not enter the order fee again per execution.

Wash-sale-adjusted dates, acquisition cost, ordinary income, gain/loss, grant-date FMV,
purchase prices, employee discounts and other broker tax fields remain ignored.

## Duplicates and atomicity

Previously imported identical broker groups are skipped automatically. The stored
fingerprint describes normalized broker facts, independent of local lot IDs and
wash-sale splits. Changed facts for the same group require correction of the saved
sale or an explicit skip; they cannot overwrite it. Additional price/date groups
for a known order require review. Manually recorded sales with the same date,
quantity, price, and currency are flagged for an explicit review/import or skip.
Version 3 exports preserve provenance so the same protection works after restoration.

Confirmation reparses the original workbook, checks all decisions, and compares a
fingerprint of current stock metadata, acquisitions, and sales with the preview.
Any intervening change requires a new preview. All selected changes and an import
receipt commit in one transaction under the stock lock. Reusing the same UUID
idempotency key and request replays the receipt; changing the request with that key
returns a conflict. A failed commit leaves no partial acquisitions, sales, or receipt.

## API

- `DELETE /api/stocks/<stock_id>/sales`: atomically delete every sale and its allocations
  for this stock. Returns `204`, including when already empty; missing or archived
  stocks/families follow the existing `404`/`410` rules.
- `POST /api/stocks/<stock_id>/import/preview`: multipart field `file`. Returns
  `format`, `file_digest`, `stock_revision`, `counts`, `grants`, `purchases`, `sales`,
  `lots`, `ignored`, `errors`, and `can_import`. Proposals carry file keys/source rows.
- `POST /api/stocks/<stock_id>/import`: multipart `file`, `stock_revision`, and
  JSON text `decisions`; UUID `Idempotency-Key` header. For E*TRADE, decisions are keyed
  by each preview sale's `key`, with optional boolean `skip`, boolean `reviewed`, and
  an `order_fee` decimal string (one consistent value for each broker order), and
  replacement `allocations` using `{vesting_id, quantity, acquisition_fmv}` or
  `{purchase_id, quantity, acquisition_fmv}`. FMV is a positive USD unit value with up
  to six decimals; fees are non-negative USD totals with up to two decimals.
  Native restores require empty decisions. Returns format and imported/skipped counts;
  `201` on commit or `200` on replay. Unresolved decisions return `400` with a preview;
  stale state or conflicting retry keys return `409`.
- `PATCH /api/stocks/<stock_id>/grants/<grant_id>`: update any subset of `title`,
  `grant_number`, `grant_date`, `approval_date`, and `taxpayer_role`. Dates use
  `YYYY-MM-DD`; approval dates must use a supported regime (on or after 8 August 2015).
  Taxpayer must be `taxpayer1` or `taxpayer2` present in the stock’s family. Nullable
  approval date, taxpayer and broker number accept null to clear. Edits are available
  through **Plans & purchases → Edit**, including for grants with recorded sales.
  Vestings, acquisition FMVs, quantities and sale allocations retain their values;
  a grant-date edit does not regenerate a schedule. Changes invalidate pending import
  and tax previews, while accepted tax helpers remain snapshots.

Both upload routes use the existing `404` missing-stock and `410` archived-stock/family
rules. Only `.xlsx` is accepted, with 10 MiB upload, 100 MiB expanded archive, and
100,000-row limits. Files are read without evaluating formulas or external links;
formula cells in imported fields, malformed workbooks, broken references, and unknown
native schema versions are rejected. No broker API requests or quote lookups occur.

## Tax preparation after import

Enable **Stock gains/losses** on a tax return to prepare the preceding year’s sales.
Missing approval date, taxpayer assignment, FMV or historical conversion rates block
acceptance. Accepted statements retain their original 2074 helper inputs and conversions
independently of the live portfolio. See the [stock-tax discussion](plans/stock-tax-preparation-discussion.md)
for the persisted workflow and API. Re-uploading existing sales for enrichment is not supported.

When Stock gains/losses is enabled, the tax estimate includes the saved reported
contributions for 3VG/3VH, 1TZ, 1UZ, 1WZ, 1TT and 1UT. Capital gains and losses are
netted across sources before simulation. Preparing a preview does not change the estimate;
accepting, editing, adding or deleting saved sources refreshes it.
