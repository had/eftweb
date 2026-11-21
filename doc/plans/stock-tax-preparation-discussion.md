# Stock tax preparation: discussion notes

Date: 11 November 2026. Updated on 13 November 2026 with the review decisions and the statement/2074 persistence requirements.

The legacy calculation logic is the validated starting point. New code is needed to use the current family, acquisition and sale models and implement the specific adaptations below. This document records the agreed scope. The [implementation plan](stock-tax-preparation-plan.md) has now been implemented; sections 8–9 describe the resolved inputs and delivered workflow.

## 1. Confirmed scope

| Topic | Decision |
| --- | --- |
| Year convention | Filing year: a **2025 tax return uses sales made in 2024**, selected using `tax_return.year - 1`. |
| Acquisitions covered | RSUs and ESPP as supported by the legacy code. |
| Nonqualifying RSUs | Excluded and rejected. No qualification-verification workflow. |
| Stock options | Excluded for now. No stock-option ownership feature. |
| Sale allocations | Use the allocations reported by E*TRADE and recorded in the current model. No FIFO reconstruction or additional validation of the tax allocation method. |
| Acquisition date | Use acquisition/vesting date for tax calculations. Release date gates sellability, which the broker enforces. |
| ESPP treatment | For the user's ESPP, tax is withheld at acquisition. Treat the acquired shares as ordinary stock using acquisition FMV as the capital-gain basis, without another employee-discount calculation. |
| Fees | Optional user input when recording a sale or importing a workbook. Omitted fees default to zero. |
| FX | Credible historical USD/EUR conversion, with optional user-entered rates. No silent stale-rate fallback. |
| Preview | Live inputs, conversions, calculations, detailed 2074 lines and proposed declaration values. No statements or helper lines are saved before acceptance; downloaded reference rates may be cached. |
| Acceptance and persistence | Explicit acceptance creates one tax statement per stock, with editable declaration contributions and persisted helper details in separate tables linked to the tax return. Users can reopen those helper views later. |
| Multiple gain/loss sources | Each source has its own statement. The tax view aggregates their contributions; reporting stock sales does not overwrite another source's values. |
| Existing development data | The application is not in production. Migration may initialize missing numeric values to zero; no production backfill or historical-format compatibility project. |
| Enrichment | Deferred. No workflow for re-uploading a workbook to enrich already imported sales or resolve enrichment conflicts. |
| Annual completeness | Deferred. Keep the current import exclusions, including `ESPP STC`; no completeness or acquisition-evidence project. |
| Tax estimation | Excluded from this feature for now. |

## 2. What changes in the current data model

The legacy helper gathers a project's sales and produces suggested 2042-C fields and a 2074 breakdown. The new feature gathers sales for the selected family and income year and follows their existing allocations to the relevant vestings or purchases.

Code references: [legacy report generation](/Users/hadrien/Projects/eftweb/taxhelpers.py:93), [legacy portfolios](/Users/hadrien/Projects/eftweb/app/stocks/portfolio.py:63), [current stock models](/Users/hadrien/Projects/eftweb/app/stocks/models.py:42).

| Information | Current state | Required adaptation |
| --- | --- | --- |
| RSU regime input | `StockGrant` stores grant date but no plan approval date. | Retain the legacy regime selection from shareholder approval date. Collect shareholder approval date and taxpayer role in Add a new grant, and show them at confirmation. Derive the supported regime from approval date. |
| RSU acquisition FMV | `GrantVesting` stores date and quantity. | Capture unit acquisition FMV from E*TRADE `Vest Date FMV`, linked to the vesting used by the sale allocation. |
| ESPP acquisition FMV | `StockPurchase` stores date, quantity and plan name. | Capture unit acquisition FMV as the tax basis. Do not substitute discounted purchase price. Use `Purchase Date Fair Mkt. Value`. |
| Acquisition versus release | The current vesting has one date. | Use it as the acquisition date. A release date is not an additional tax-reporting input. |
| Sale fees | Gross USD proceeds per share and allocations exist; fees do not. | Add an optional total fee for the sale in USD, defaulting to zero. Allocate it once across its reporting lines. |
| Conversion inputs | The old converter supplies rates during calculation. | Use a maintained historical rate table and optional manual rates. Show dates, rate direction and converted amounts in the preview and persist the accepted conversion details with the helper lines. |
| Source statements | Current family tax returns have no stock-tax statements. | Add a statement per gain/loss source linked to the tax return. Reporting a year of sales creates one per stock, with that stock's accepted, editable declaration contributions. |
| 2074 helper lines | The legacy helper generates detailed lines but the current tax-return model does not store them. | Add a separate table for statement-owned helper lines, including accepted acquisition/sale inputs, EUR amounts, conversions, fees and calculation results. |

Acquisition FMV is a unit value. If 20 shares are sold from a 100-share vesting, the calculation uses the FMV of those 20 shares. The import must not replace the vesting's quantity with the quantity sold.

For development records, zero initialization is acceptable. A zero used as a migration placeholder for FMV should be shown as missing acquisition FMV in the preview, distinguishing it from the optional zero-fee default. Existing development sales remain usable for holdings. New manual sales and selected broker imports require positive acquisition FMV; import preview supplies an input when it is absent. Missing grant metadata or FX blocks acceptance of the entire annual preparation. Optional fees default to zero. No backfill or enrichment system is included.

## 3. Calculation adaptations

Most legacy behavior can be carried over. The agreed changes are specific:

- **Losses:** include loss-making sales and report their effect correctly. Ordinary-share/ESPP capital losses contribute to the capital-gain/loss calculation. For qualifying RSUs sold below acquisition value, reduce the corresponding acquisition gain before allowances rather than counting the same decline again as an ordinary capital loss. The existing helper leaves acquisition gain unchanged in this situation. [Declaration instructions, page 112](https://www.impots.gouv.fr/www2/fichiers/documentation/brochure/ir_2026/pdf_som/06-traitements_salaires_85a114.pdf).
- **EUR 300,000 acquisition-gain threshold:** apply the annual threshold to the relevant RSU regimes and report the excess separately. The installed helper applies the post-2018 50% allowance to the entire acquisition gain, including a tested EUR 400,000 example. [Official regime summary](https://www.impots.gouv.fr/particulier/questions/mon-entreprise-ma-attribue-des-actions-gratuites-comment-sera-impose-le-gain).
- **Acquisition FMV:** use imported acquisition FMV for both RSUs and ESPP, converted at acquisition date. Convert sale proceeds at sale date.
- **Fees:** carry the optional sale fee through the calculation and report it once. The legacy `sell_rsus` and `sell_espp` entry points currently set selling fees to zero.
- **FX:** replace the stale-history fallback with covered historical rates or an explicit user-entered rate.

Calculate annual rules across the relevant year's stock sales before distributing results into stock statements. In particular, creating one statement per stock must not restart the EUR 300,000 threshold for each stock. Persist each stock's contribution and the threshold calculation details needed to explain it.

The existing `1TZ`, `1UZ`, `1WZ`, `3VG` and `3VH` outputs remain the starting point. One precise consequence of supporting the threshold is that **RSU acquisition gain above the threshold also uses `1TT`/`1UT`**, even though stock options are excluded. Keep those final boxes editable. This does not require a stock-option ownership subsystem; each grant’s `taxpayer_role` assigns RSU excess to the appropriate box. [Declaration instructions, page 112](https://www.impots.gouv.fr/www2/fichiers/documentation/brochure/ir_2026/pdf_som/06-traitements_salaires_85a114.pdf).

## 4. Concrete findings retained after review

The following findings concern exact code behavior. They do not reopen the validated calculation logic generally.

### Regime boundary comparisons

The issue is an inclusive comparison in `_determine_rsu_plans_type`, not a claim that the statutory dates have recently changed. The installed helper uses `<= 2015-08-08`, `<= 2017-01-01` and `<= 2018-01-01` as upper bounds.

| Approval date | Installed helper returns | Regime for that date |
| --- | --- | --- |
| 8 August 2015 | `QUALIFIED_RSU` | `MACRON_1_RSU` |
| 31 December 2016 | `MACRON_1_RSU` | `MACRON_2_RSU` |
| 1 January 2017 | `MACRON_1_RSU` | `MACRON_2_RSU` |
| 1 January 2018 | `MACRON_2_RSU` | `MACRON_3_RSU` |

These results were reproduced by calling the installed helper. The official periods are 8 August 2015–30 December 2016, 31 December 2016–31 December 2017, and from 1 January 2018. Correct the comparisons when carrying this selection into the new code. [Official date ranges, pages 111–112](https://www.impots.gouv.fr/www2/fichiers/documentation/brochure/ir_2026/pdf_som/06-traitements_salaires_85a114.pdf).

Code reference: [installed regime selector](/Users/hadrien/Projects/eftweb/.venv/lib/python3.14/site-packages/easyfrenchtax/stock_helper.py:76).

### Exactly which regimes are unsupported

Calling `compute_acquisition_gain_tax` with each enum value confirmed that it accepts `MACRON_1_RSU`, `MACRON_2_RSU` and `MACRON_3_RSU`, and raises `Unsupported tax scheme` for both `NONQUALIFIED_RSU` and `QUALIFIED_RSU`.

The legacy selector labels dates through 27 September 2012 as `NONQUALIFIED_RSU` and dates from 28 September 2012 through 8 August 2015 as `QUALIFIED_RSU`. These are its internal labels, not a general assertion about the legal qualification of every plan. After correcting the boundary above, approvals before 8 August 2015 remain outside the supported date-based regimes. Reject them clearly before calculation. Nonqualifying plans are separately excluded by the scope decision.

Code reference: [supported acquisition-gain branches and rejection](/Users/hadrien/Projects/eftweb/.venv/lib/python3.14/site-packages/easyfrenchtax/stock_helper.py:342).

### Unit rounding before calculating a sale-line total

The earlier generic rounding warning is replaced with a reproducible example. `sell_espp` and `sell_rsus` round unit acquisition value to two decimals before `compute_capital_gain_tax` multiplies it by quantity. The legacy portfolio also rounds converted unit sale price and acquisition value before passing them to the helper.

For 1,000 shares with a converted unit acquisition FMV of **EUR 100.0049** and unit sale proceeds of **EUR 110**:

| Calculation | Acquisition total, rounded to euros | Reported gain |
| --- | --- | --- |
| Installed helper: unit value becomes EUR 100.00 before multiplication | EUR 100,000 | EUR 10,000 |
| Preserve unit precision, multiply, then round the acquisition-total line | EUR 100,005 | EUR 9,995 |

The EUR 5 difference is caused before whole-euro sale-line rounding. This is the specific precision issue; it does not challenge the required rounding of declaration lines. The new calculation should preserve source/conversion precision until the applicable reporting-line rounding step.

Code references: [ESPP unit rounding](/Users/hadrien/Projects/eftweb/.venv/lib/python3.14/site-packages/easyfrenchtax/stock_helper.py:247), [RSU unit rounding](/Users/hadrien/Projects/eftweb/.venv/lib/python3.14/site-packages/easyfrenchtax/stock_helper.py:297), [multiplication and line rounding](/Users/hadrien/Projects/eftweb/.venv/lib/python3.14/site-packages/easyfrenchtax/stock_helper.py:391), [legacy converted sale price](/Users/hadrien/Projects/eftweb/app/stocks/portfolio.py:98).

## 5. Credible USD/EUR conversion

The installed converter's bundled USD history ends on **9 May 2025**. The legacy code enables out-of-range fallback, which can reuse an old rate for a later transaction. Replacing this behavior is a confirmed requirement.

The implemented source is the **ECB historical reference-rate series**, published as currencies per euro and available as time-series downloads. A local conversion table retains publication date, rate and source, fetching history on first use or when required coverage is unavailable. A failed fetch can reuse covered cached dates. [ECB reference rates and historical downloads](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html).

For an ECB USD rate expressed as USD per EUR, convert using `EUR amount = USD amount / rate`. Acquisition FMV and sale proceeds need rates for their respective dates. The preview should show the event date, selected rate date, direction, rate source and resulting EUR amount.

Optional user input can supply or override an acquisition-date or sale-date rate. Clearly label a manual rate and use an explicit direction such as “EUR per USD.” A missing historical rate must require a table update or manual input, rather than silently reusing the last rate in the table.

For weekends and publication holidays, use the latest published rate on or before the event date within seven calendar days, and only within downloaded coverage. Manual overrides are keyed by event date, affect only that preparation, and never update the shared reference table.

## 6. Live preview, persisted 2074 helpers and source statements

The purpose is to help the user enter the online tax return, including the lengthy Cerfa 2074 declaration of realized gains and losses. Annual box totals alone are insufficient. Preserve the legacy helper's detailed sale-line output alongside the proposed 2042-C contributions.

### Detailed 2074 helper output

The preview uses the selected family's recorded sales for the income year, across its stocks, including historical transactions for archived stocks. Group the helper by stock and show every RSU sale line with its acquisition allocation. A sale spanning different vestings or acquisition FMVs needs separate detail lines so that each unit acquisition value remains identifiable. Include the corresponding ESPP sale details as well.

Each helper line must show the values the user needs to enter, with clear form labels or box/line references:

- Stock/security identification, acquisition type, acquisition date and sale date.
- Number of shares sold from the acquisition lot.
- Unit acquisition FMV and unit selling price in EUR, with the original USD values and acquisition/sale conversion rates available alongside them.
- Total gross sale proceeds, optional allocated selling fees and net sale proceeds.
- Total acquisition basis and the resulting gain or loss, with reporting-line rounding visible.
- The associated RSU acquisition-gain calculation, applicable allowance, threshold treatment and resulting declaration contributions.

Keep the legacy 2074 field structure as the reference: security name `511`, sale date `512`, unit selling price `514`, quantity `515`, gross proceeds `516`, selling fees `517`, net proceeds `518`, unit acquisition value `520`, acquisition total `521`, acquisition fees where applicable `522`, total basis `523` and result `524`. This is a helper for entering the form, not an automatic filing or a requirement to generate a PDF.

Code reference: [legacy detailed 2074 output](/Users/hadrien/Projects/eftweb/.venv/lib/python3.14/site-packages/easyfrenchtax/stock_helper.py:369).

### Acceptance and saved helper views

Before acceptance, the preview and edits are temporary. On explicit acceptance, create **one tax statement per stock** in the selected tax return and persist its detailed helper lines in a separate child table. Save the values used for the accepted calculation, including original amounts, rates, rate dates, EUR conversions, fees, rounded line results and declaration contributions. A link to the live stock records alone is insufficient: users must be able to reopen the accepted helper details later even if acquisition values, transactions or the conversion table change.

Statement-level declaration contributions are editable before acceptance and afterwards. Show the computed suggestions alongside edited contributions so that the helper remains understandable if the user overrides a suggested amount. Persist those accepted contributions and helper details together. Preview recalculation must not silently replace saved statements or manual edits. No revision-history system or tax-estimation integration is included.

### Aggregation without overwriting other sources

Each source of capital gain or loss has a separate statement. Reporting all recorded sales for an income year creates one stock statement per stock, rather than writing directly into shared tax-return boxes. Other sources keep their own statements and can coexist with the stock statements. A manually entered gain/loss source follows the same statement principle.

The tax view aggregates statement contributions into the final declaration fields. Retain each source's signed capital result, combine gains and losses, and present the resulting net gain or net loss for the relevant capital-gain/loss box. Aggregate acquisition-gain and allowance contributions into their respective boxes. Show which statements contributed to each total.

For example, a stock statement contributing a EUR 1,000 capital gain and another source contributing a EUR 300 capital loss produce a EUR 700 net capital gain in the tax view. Neither source is overwritten. An explicit edit to a source statement changes the aggregate without obscuring that source's saved helper details.

Re-reporting the same stock and income year must identify its existing generated statement, so repeated acceptance cannot accidentally double count the same sales. A new preparation lists the complete generated set that will be replaced, including obsolete statements with no remaining sales. Explicit replacement confirmation is required. Acceptance replaces this set atomically; manual sources remain untouched.

Code references: [tax-return model](/Users/hadrien/Projects/eftweb/app/family/models.py:89), [tax-return detail view](/Users/hadrien/Projects/eftweb/frontend/src/views/TaxReturnDetailView.vue).

## 7. E*TRADE import changes within this scope

The current importer matches existing lots and creates sales, but ignores acquisition FMV. Extend a **new sale import** to capture the acquisition FMV used by its allocation. Updating already imported sales through a separate enrichment upload is deferred.

The reference workbook's headers have already been inspected. Only the following fields are relevant to this discussion:

| E*TRADE column(s) | Use |
| --- | --- |
| `Vest Date`, `Vest Date FMV` | RSU acquisition date and unit acquisition FMV. Match to the existing vesting using grant number plus vest date. |
| `Purchase Date Fair Mkt. Value` | Confirmed ESPP unit acquisition FMV; discounted purchase price is ignored. |
| `Grant Date`, `Grant Number` | Keep the existing grant cross-check and source matching. Approval date remains a separate input. |
| `Total Proceeds`, `Proceeds Per Share`, `Date Sold`, `Order Number` | Keep the existing sale facts, grouping and proceeds cross-check. |

Do not add imports for purchase price, employee discount, grant-date FMV, ordinary income, adjusted cost basis, US qualification/election fields or wash-sale calculations. Existing purchase-date matching remains in use.

The workbook has no explicit fee or currency column. Retain USD for this import format and add an **optional fee input in the import preview**, defaulting to zero. Enter one total fee per broker order. Apportion it across every execution in the workbook by gross proceeds, using deterministic cent allocation before applying skips or duplicate detection. Skipped/duplicate executions retain their share rather than transferring it to new sales. Each sale’s fee is then allocated across its acquisition lines by gross proceeds. Manual sale entry gets the same optional total-fee field.

Capture FMV at source-row/lot level before grouping executions. Different source vestings or purchases can have different acquisition FMVs even when they belong to the same sale. Require repeated values for the same source lot to agree within the selected new import; do not average unrelated FMVs or change acquisition quantities.

Store acquisition FMV with the corresponding vesting or purchase. A new sale import can populate that value as part of the same transaction. If a nonzero value already differs, report the specific conflict instead of adding a reconciliation/enrichment workflow. Manual splits carry FMV explicitly for each selected lot; an existing nonzero lot value is reused and cannot be overwritten through sale import.

Keep preview read-only, preserve lot-quantity checks and atomic confirmation, and validate imported FMV as a finite decimal without evaluating workbook formulas. The existing ignored-row behavior remains unchanged. There is no requirement to preserve old workbook versions, hashes or receipts through this development migration beyond keeping the new import's duplicate and retry behavior correct.

Code references: [workbook parser](/Users/hadrien/Projects/eftweb/app/stocks/import_parsers.py), [matching and persistence](/Users/hadrien/Projects/eftweb/app/stocks/import_service.py), [upload API](/Users/hadrien/Projects/eftweb/app/api/stock_import.py).

## 8. Resolved implementation choices

| Topic | Implemented behavior |
| --- | --- |
| Grant metadata | Shareholder approval date and `taxpayer1`/`taxpayer2` in Add a new grant and its confirmation; selected taxpayer must exist in the family. Unknown development metadata remains unset. |
| ESPP column | `Purchase Date Fair Mkt. Value`, retained separately from the ignored discounted purchase price. |
| Fees | Optional USD total on manual sale entry; one total per broker order in import preview, apportioned across all workbook executions before skips. |
| Non-publication dates | Latest preceding published ECB rate within seven days and within downloaded coverage. Optional EUR-per-USD overrides apply to the preparation only. |
| Annual threshold | One EUR 300,000 threshold per taxpayer across Macron II/III gains after loss adjustments. Sale-date order, then symbol, sale ID and allocation ID break ties; the crossing allocation is divided into eligible gain and excess. Macron I does not consume it. |
| RSU threshold excess | Grant taxpayer selects `1TT` or `1UT`. |
| Repeat reporting | Explicit replacement of the full generated set, including obsolete-statement removal; manual statements remain unchanged. |
| Output | Snapshot statements and separate helper rows saved atomically; reported contributions remain editable independently of computed suggestions. |
| Native interchange | Schema version 3 round-trips approval date, taxpayer, acquisition FMV and selling fees. Historical-format compatibility is not a feature requirement. |

## 9. Delivered workflow and API

Enable **Stock gains/losses** in the tax return’s information groups, then choose **Prepare stock sales**. Preview includes every recorded sale in the family’s preceding calendar year, including archived stocks. It shows precise blocking errors, per-taxpayer threshold usage, editable stock contributions and expandable, copyable 2074 fields `511–524`.

Acceptance recalculates on the server and checks a revision covering source records, reference rates and existing statements. All stocks and their helper snapshots commit together. A changed source requires a new preview; repeated acceptance with the same UUID idempotency key returns the existing receipt. Optional manual gain/loss sources have a name and signed capital result. Aggregates net all reported capital results into `3VG` or `3VH` and sum the acquisition-gain/allowance boxes. They do not feed the partial tax estimate.

Existing grants can be corrected through **Plans & purchases → Edit**: title, broker grant number, individual grant date, shareholder approval date and taxpayer. These metadata edits preserve vestings and recorded sales, invalidate pending preparations, and do not change accepted helper snapshots.

Saved **View / edit** opens the accepted helper, original USD inputs, conversion evidence and rounded EUR reporting fields. Contribution edits update aggregates and preserve computed suggestions and helper rows. Live transaction or reference-rate edits cannot change saved helpers.

Tax-return-scoped endpoints:

- `GET/POST /api/tax-returns/<id>/capital-gain-statements`: list sources and aggregates, or create a named manual source.
- `GET/PUT/DELETE /api/tax-returns/<id>/capital-gain-statements/<statement_id>`: read saved details, edit reported contributions/source name, or delete a statement and its helpers.
- `POST /api/tax-returns/<id>/stock-tax/preview`: optional `fx_overrides` mapping ISO dates to EUR-per-USD decimal strings.
- `POST /api/tax-returns/<id>/stock-tax/accept`: `source_revision`, optional `fx_overrides`, `reported` keyed by stock ID, and `replace_existing`; UUID `Idempotency-Key` header.

Migration `ef2a91c7d430` adds tax inputs, reference-rate storage, source statements, helper rows and acceptance receipts. Existing monetary additions become zero; unknown approval dates and taxpayers stay null. These incomplete records retain their holdings behavior but cannot be accepted as a tax preparation.

Stock options, nonqualifying/older unsupported RSUs, enrichment, annual completeness, loss carryforwards, estimation and PDF generation remain outside this implementation.
