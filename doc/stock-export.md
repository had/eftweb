# Stock XLSX export, versions 1 and 2

The stock detail page's **Export** button downloads all persisted records for the
current stock, including future vestings and sales outside the current year filter.
`GET /api/stocks/<stock_id>/export` returns an XLSX attachment named
`<sanitized-symbol>-export.xlsx` with `Cache-Control: no-store`. Missing stocks return
JSON 404; archived stocks or families return JSON 410; export failures return JSON 500.

There are exactly two worksheets, in this order: `Plans & vestings`, then `Sales`.
Column names, worksheet names, and metadata keys are part of the interchange contract.
New downloads use version 2. The importer continues to accept version 1 files.
The export reads one database snapshot and does not fetch stock quotes.

## Metadata and cell types

On `Plans & vestings`, rows 1–4 are two-column key/value pairs:

| Row | Column A | Column B |
| --- | --- | --- |
| 1 | `export_format` | `eftweb.stock` |
| 2 | `schema_version` | numeric `2` (`1` in older files) |
| 3 | `stock_name` | the stock's name |
| 4 | `stock_symbol` | the stock's ticker |

Row 5 is blank; row 6 contains the table headers. On `Sales`, row 1 contains
the table headers. Empty stocks still include metadata and both table headers.

- All dates are literal text in `YYYY-MM-DD` format.
- Proceeds per share are literal decimal text with exactly six fractional digits.
- Quantities are whole numbers. Values with 16 or more digits are stored as decimal
  text to prevent Excel's 15-digit numeric precision from changing them. Importers
  must accept both numeric integers and integer text.
- `customized` is an Excel boolean. Non-applicable cells are blank, not zero.
- Strings are literal text, including formula-like names and Excel error-like names.
- Keys are opaque text identifiers, currently prefixed `grant:`, `vesting:`,
  `purchase:`, or `sale:`. Treat the complete key as an identifier within the file;
  never reuse it as a destination database ID or infer identity from a plan name.

## Plans & vestings

Headers, in order:

`record_type`, `grant_key`, `plan_name`, `grant_date`, `grant_quantity`,
`vesting_start_date`, `schedule_type`, `customized`, `vesting_key`, `vesting_date`,
`vesting_quantity`, `purchase_key`, `purchase_date`, `purchase_quantity`.

Version 2 appends `grant_number`. This is nullable literal text, repeated on each
RSU grant/vesting row, and blank on purchase rows. Leading zeros are preserved.

- `rsu_vesting`: one row per vesting. The grant's complete fields are repeated on
  each of its rows. `plan_name` is the grant title; `grant_quantity` is the entire
  grant, not this row's vested quantity. Purchase fields are blank.
- `rsu_grant`: a grant with no vestings. Grant fields are populated and vesting and
  purchase fields are blank. Normal grant entry requires vestings; this row type
  preserves any grant-only records already in the database.
- `stock_purchase`: one row per completed purchase, including ESPP and other plan
  names. Only `record_type`, `plan_name`, and the three purchase fields are populated.

Grants are ordered by grant date then source ID, with each grant's vestings ordered
by vesting date then source ID. Purchases follow, ordered by purchase date then
source ID. Distinct grants, vestings, and purchases retain distinct keys even if
their names, dates, or quantities are identical. Scheduled vestings are never
regenerated from schedule type: the explicitly exported releases are authoritative.

## Sales

Headers, in order:

`sale_key`, `transaction_date`, `sale_quantity`, `proceeds_per_share`, `currency`,
`vesting_key`, `purchase_key`, `allocation_quantity`.

Version 2 appends `import_source`, `source_order_number`, `source_fingerprint`.
These are all blank for manual sales, or `etrade`, the literal broker order number,
and a SHA-256 fingerprint of normalized broker sale facts. All three fields repeat
across a sale's allocation rows. A broker group is identified by stock, import
source, order number, transaction date, exact price, and currency. The fingerprint
is independent of local database IDs, file row order, and wash-sale row splitting.

One row represents one allocation of a sale to an acquisition lot. The complete
sale fields are repeated on each row. Exactly one of `vesting_key` or `purchase_key`
identifies the source lot in `Plans & vestings`. `allocation_quantity` is the shares
sold from that lot; `sale_quantity` is the entire sale and must not be summed across
repeated rows. Similarly, repeated grant quantities must not be summed per vesting.

Sales are ordered by transaction date then source ID. Within each sale, vesting
allocations precede purchase allocations, each ordered by source lot ID. A sale with
no allocations is preserved as one row with blank source and allocation fields;
normal sale entry requires allocations.

## Import and exclusions

The importer checks the format/version and requires an existing empty destination
stock with the same ticker. It groups grants by `grant_key`, creates their exact
vestings and purchases, and maps every file key to a newly generated destination ID.
Sales are grouped by `sale_key`, with allocation references remapped through those mappings. Repeated fields within
one grant or sale must agree. New creation tokens and request hashes belong to the
destination instance and are intentionally absent from the file.

The format excludes legacy project-based tax portfolios,
other stocks and family personal data, derived summaries, cached quotes, and UI state.
Recreated records yield the same acquisition quantities, allocations, and remaining
lot balances; date-dependent summaries need the same valuation date and market-value
estimates depend on the destination's live quote.
