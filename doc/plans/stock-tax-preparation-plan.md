# Stock tax preparation and persisted declaration helpers

## 1. Summary

Build a tax-return preparation workflow for recorded RSU and ESPP sales, using the updated [discussion document](/Users/hadrien/Projects/eftweb/doc/plans/stock-tax-preparation-discussion.md) and the decisions made here.

A filing-year return uses the preceding calendar year’s sales. Preparation covers all the family’s stocks, including archived stocks with relevant transactions, and produces:

- Detailed, copyable Cerfa 2074 helper lines.
- Editable declaration contributions, grouped into one statement per stock.
- Aggregated declaration boxes combining stock statements with other gain/loss statements.

Preview is temporary. Acceptance saves all generated stock statements and their helper details together. Re-reporting explicitly replaces the previously generated statements after review, preserving manually entered sources.

Stock options, nonqualifying and unsupported RSU regimes, enrichment uploads, annual-completeness checks, loss carryforwards, tax estimation and PDF generation remain outside this implementation.

## 2. Data entry, model changes and imports

**RSU grants**

- Add shareholder `approval_date` and `taxpayer_role` (`taxpayer1` or `taxpayer2`) to grants.
- Collect both in the existing **Add a new grant** modal and display them in its confirmation step.
- Validate the selected taxpayer against the family. Derive the regime from approval date using corrected boundaries: Macron I from 8 August 2015, Macron II from 31 December 2016, Macron III from 1 January 2018. Reject unsupported earlier dates.
- Keep acquisition dates distinct from approval dates and release/sellability dates.

**Acquisition FMV and sale fees**

- Add USD unit acquisition FMV to vestings and purchases, preserving six decimal places.
- Collect FMV for each selected acquisition lot in manual sale entry. Reuse an already recorded value; otherwise require user input and save it with the sale.
- Add an optional total USD selling fee to manual sales, defaulting to zero.
- Save new sales and their acquisition values atomically. Reject a conflicting nonzero FMV for the same lot rather than introducing an enrichment workflow.

**E*TRADE import**

- Read RSU FMV from `Vest Date FMV` and ESPP FMV from `Purchase Date Fair Mkt. Value`. Continue using existing source matching and unadjusted acquisition dates.
- Preserve row-level acquisition FMV before grouping executions. Never average FMVs from different lots.
- For missing FMV, provide an input in import preview. Require a value before importing that sale, or allow the sale to be skipped.
- Add one optional fee input per broker order. Apportion it across execution groups and acquisition lines by gross proceeds, using deterministic cent allocation so the allocated amounts sum exactly to the entered fee.
- Apportion order fees across all corresponding executions in the workbook before applying skips; skipped or duplicate executions must not transfer their fee share to newly imported executions.
- Keep existing duplicate detection, quantity validation, read-only preview and atomic confirmation.
- Ignore the previously excluded broker tax columns and `ESPP STC` rows.

Extend manual/import API payloads and frontend stores with these fields. Update native stock export/import to round-trip approval date, taxpayer, acquisition FMV and fees under a new schema version; historical workbook compatibility is not required.

**Development migration**

Initialize existing monetary additions to zero. Leave unknown approval dates and taxpayer assignments unset rather than inventing them. Incomplete development records remain usable for holdings but cannot produce accepted tax preparations; no backfill or correction-editor project is included.

## 3. Calculation engine and historical conversion

Implement a new calculation service for the current models, using the validated legacy behavior as its reference. Do not modify the installed library.

- Follow recorded sale allocations. Produce a separate helper line for each sale/acquisition allocation, preserving stock, grant, taxpayer and acquisition identity.
- Use acquisition FMV for both RSUs and ESPP. ESPP contributes ordinary capital gains/losses without another employee-discount calculation.
- Calculate RSU acquisition gain separately from disposal gain. Apply corresponding RSU losses before allowances and the annual threshold, without counting the absorbed loss again as an ordinary capital loss. Preserve any remaining reportable loss. [Official treatment](https://bofip.impots.gouv.fr/bofip/5654-PGP.html/identifiant=BOI-RSA-ES-20-20-20-20260521).
- Apply one €300,000 threshold per taxpayer across eligible Macron II/III gains after loss adjustments. Consume it in sale-date order; break same-day ties by stock symbol, sale ID and allocation ID. Split the crossing line. Macron I gains do not consume this threshold.
- Preserve the legacy holding-period allowances. Route threshold excess to `1TT` or `1UT` according to the grant’s taxpayer.
- Use decimal arithmetic throughout. Preserve unit-price and conversion precision until reporting-line rounding, use half-up rounding, and derive annual capital results from the rounded reporting lines.

**FX service**

- Maintain a local daily USD/EUR rate table populated from the [ECB historical reference-rate downloads](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html).
- Fetch history on first use and refresh when required coverage is unavailable. Reuse covered cached dates if fetching fails.
- Use acquisition-date rates for FMV and sale-date rates for proceeds and allocated fees.
- On a non-publication day, use the latest preceding published rate within seven calendar days. Never extrapolate beyond available coverage.
- Allow preview overrides keyed by event date, explicitly entered as **EUR per USD**. Overrides affect that preparation, not the shared reference table.
- Show original amounts, conversion direction, requested date, effective rate date, source and EUR result. Missing coverage without a manual rate blocks acceptance.

Missing FMV, approval date, taxpayer assignment or conversion rate must produce precise errors and block acceptance of the yearly preparation.

## 4. Statements, saved helpers, APIs and interface

**Persistence**

Add:

- A gain/loss statement table linked to the tax return, distinguishing generated stock statements from manually entered sources. Generated statements identify their stock and retain computed suggestions separately from editable reported contributions.
- A separate statement-owned helper-line table containing accepted source inputs, conversion details, rounded 2074 fields, RSU calculations and taxpayer information.

Use a signed capital result per statement, alongside acquisition-gain/allowance contributions. Saved helpers contain the actual accepted values, not merely references to live transactions, so later stock or rate changes cannot alter them.

Manual source statements require a source name and signed capital gain/loss. They have no generated helper lines.

**APIs**

Add tax-return-scoped operations for:

- Listing statements and aggregated declaration values.
- Creating, editing and deleting manual source statements.
- Reading saved statement/helper details, editing reported contributions and deleting generated statements.
- Preparing all stock sales for the return’s income year.
- Accepting the complete preparation, including edited contributions and explicit replacement confirmation.

Preview returns proposed statements, detailed lines, missing-input errors, existing statements affected by replacement and a source revision. Acceptance recalculates server-side, checks that revision, and saves atomically. Reject stale previews and make acceptance retries idempotent.

Replacement applies to the year’s generated stock-statement set, including removal of obsolete generated statements whose sales no longer exist. Show all replacements/removals before confirmation. Manual statements remain untouched.

**Tax-return interface**

- Add a configurable **Stock gains/losses** information group, following existing statement-group conventions.
- Provide **Prepare stock sales**, manual-source entry, saved statement listing and aggregate declaration boxes.
- Group preparation by stock, with expandable sale/allocation details and editable proposed statement contributions.
- Show the legacy 2074 fields `511–524`, including EUR unit acquisition/selling values, quantities, proceeds, fees, acquisition basis and gain/loss. Provide clear labels and copy controls.
- Display per-taxpayer threshold usage and each stock’s contribution.
- Save all stocks through one acceptance action. Require explicit confirmation when saved generated statements or edits will be replaced.
- Reopen persisted helpers from saved statements. Subsequent contribution edits update aggregates while preserving the computed helper details.

Aggregate signed capital results into the net gain or loss box, and sum acquisition-gain/allowance contributions into their respective boxes. Keep computed and edited amounts visibly distinguishable. Do not feed these statements into tax estimation.

## 5. Tests and acceptance criteria

**Calculation tests**

- Filing-year selection; partial vesting sales; multiple acquisitions in one sale; mixed RSU/ESPP sales.
- Every regime boundary and rejection of unsupported regimes.
- Two- and eight-year holding-period boundaries.
- Ordinary losses and RSU losses, including no double counting.
- Threshold below, exactly at and above €300,000; multiple stocks; two taxpayers; sale-date ordering and crossing-line splits.
- Optional fees allocated exactly once, and the documented €5 unit-rounding example.

**Import and FX tests**

- Both confirmed FMV columns, user-supplied missing FMV, repeated-lot conflicts and unchanged source quantities.
- Order fees spanning executions, allocations, skipped sales and duplicates.
- Import rollback, retry behavior and new native-format round trips.
- ECB parsing and rate direction; acquisition versus sale dates; seven-day boundary; missing coverage; network failure with covered cache; manual overrides.

**Persistence and workflow tests**

- Preview creates no statements or helper rows.
- Acceptance creates one statement per stock and saves helpers atomically.
- Saved helpers remain unchanged after source transactions or rates change.
- Manual gain/loss sources aggregate correctly with stock statements.
- Edited reported contributions preserve computed suggestions.
- Explicit replacement, obsolete-statement removal, stale-preview rejection and retry protection.
- Tax-return/family isolation and existing archive restrictions.

Run the backend suite, frontend tests and frontend production build. Verify the new section, preparation form, replacement confirmation and saved 2074 helper views in the browser. Update the discussion/import documentation to reflect the implemented behavior.
