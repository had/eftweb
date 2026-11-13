# Stock tax preparation: discussion notes

Date: 11 November 2026. Updated with the review decisions.

The legacy calculation logic is the validated starting point. New code is needed to use the current family, acquisition and sale models and implement the specific adaptations below. This document records the agreed scope and remaining concrete questions. It is not an implementation plan.

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
| Preview | Live, non-persisted inputs, conversions, calculations and proposed declaration values. |
| Acceptance | Final declaration fields are editable. Only explicit acceptance commits those values to the selected tax return. |
| Existing development data | The application is not in production. Migration may initialize missing numeric values to zero; no production backfill or historical-format compatibility project. |
| Enrichment | Deferred. No workflow for re-uploading a workbook to enrich already imported sales or resolve enrichment conflicts. |
| Annual completeness | Deferred. Keep the current import exclusions, including `ESPP STC`; no completeness or acquisition-evidence project. |
| Tax estimation | Excluded from this feature for now. |

## 2. What changes in the current data model

The legacy helper gathers a project's sales and produces suggested 2042-C fields and a 2074 breakdown. The new feature gathers sales for the selected family and income year and follows their existing allocations to the relevant vestings or purchases.

Code references: [legacy report generation](/Users/hadrien/Projects/eftweb/taxhelpers.py:93), [legacy portfolios](/Users/hadrien/Projects/eftweb/app/stocks/portfolio.py:63), [current stock models](/Users/hadrien/Projects/eftweb/app/stocks/models.py:42).

| Information | Current state | Required adaptation |
| --- | --- | --- |
| RSU regime input | `StockGrant` stores grant date but no plan approval date. | Retain the legacy regime selection from shareholder approval date. Provide that distinct date, or an explicitly selected supported regime; the input choice remains for planning. |
| RSU acquisition FMV | `GrantVesting` stores date and quantity. | Capture unit acquisition FMV from E*TRADE `Vest Date FMV`, linked to the vesting used by the sale allocation. |
| ESPP acquisition FMV | `StockPurchase` stores date, quantity and plan name. | Capture unit acquisition FMV as the tax basis. Do not substitute discounted purchase price. Confirm the exact E*TRADE column with the user at planning time if needed. |
| Acquisition versus release | The current vesting has one date. | Use it as the acquisition date. A release date is not an additional tax-reporting input. |
| Sale fees | Gross USD proceeds per share and allocations exist; fees do not. | Add an optional total fee for the sale in USD, defaulting to zero. Allocate it once across its reporting lines. |
| Conversion inputs | The old converter supplies rates during calculation. | Use a maintained historical rate table and optional manual rates. Show dates, rate direction and converted amounts in the preview. |
| Declaration values | Current family tax returns have no stock-tax fields. | Store the accepted, editable declaration values on the tax return. Do not store a separate preparation snapshot. |

Acquisition FMV is a unit value. If 20 shares are sold from a 100-share vesting, the calculation uses the FMV of those 20 shares. The import must not replace the vesting's quantity with the quantity sold.

For development records, zero initialization is acceptable. A zero used as a migration placeholder for FMV should be shown as missing acquisition FMV in the preview, distinguishing it from the optional zero-fee default. The user can still record sales while acquisition data is incomplete and edit final declaration fields before acceptance. This does not require a backfill or enrichment system.

## 3. Calculation adaptations

Most legacy behavior can be carried over. The agreed changes are specific:

- **Losses:** include loss-making sales and report their effect correctly. Ordinary-share/ESPP capital losses contribute to the capital-gain/loss calculation. For qualifying RSUs sold below acquisition value, reduce the corresponding acquisition gain before allowances rather than counting the same decline again as an ordinary capital loss. The existing helper leaves acquisition gain unchanged in this situation. [Declaration instructions, page 112](https://www.impots.gouv.fr/www2/fichiers/documentation/brochure/ir_2026/pdf_som/06-traitements_salaires_85a114.pdf).
- **EUR 300,000 acquisition-gain threshold:** apply the annual threshold to the relevant RSU regimes and report the excess separately. The installed helper applies the post-2018 50% allowance to the entire acquisition gain, including a tested EUR 400,000 example. [Official regime summary](https://www.impots.gouv.fr/particulier/questions/mon-entreprise-ma-attribue-des-actions-gratuites-comment-sera-impose-le-gain).
- **Acquisition FMV:** use imported acquisition FMV for both RSUs and ESPP, converted at acquisition date. Convert sale proceeds at sale date.
- **Fees:** carry the optional sale fee through the calculation and report it once. The legacy `sell_rsus` and `sell_espp` entry points currently set selling fees to zero.
- **FX:** replace the stale-history fallback with covered historical rates or an explicit user-entered rate.

The existing `1TZ`, `1UZ`, `1WZ`, `3VG` and `3VH` outputs remain the starting point. One precise consequence of supporting the threshold is that **RSU acquisition gain above the threshold also uses `1TT`/`1UT`**, even though stock options are excluded. Keep those final boxes editable. This does not require a stock-option ownership subsystem; assigning an RSU excess between those boxes is a reporting question for planning. [Declaration instructions, page 112](https://www.impots.gouv.fr/www2/fichiers/documentation/brochure/ir_2026/pdf_som/06-traitements_salaires_85a114.pdf).

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

A concrete source proposal is the **ECB historical reference-rate series**, published as currencies per euro and available as time-series downloads. A local conversion table can retain publication date, rate and source. [ECB reference rates and historical downloads](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html).

For an ECB USD rate expressed as USD per EUR, convert using `EUR amount = USD amount / rate`. Acquisition FMV and sale proceeds need rates for their respective dates. The preview should show the event date, selected rate date, direction, rate source and resulting EUR amount.

Optional user input can supply or override an acquisition-date or sale-date rate. Clearly label a manual rate and use an explicit direction such as “EUR per USD.” A missing historical rate must require a table update or manual input, rather than silently reusing the last rate in the table.

For weekends and publication holidays, the proposed rule is the latest published rate on or before the event date, within a defined short lookback. Confirm that choice during planning. It must remain distinct from an out-of-coverage fallback.

## 6. Live preview and acceptance into a tax return

The preview uses the selected family's recorded sales for the income year, across its stocks, including historical transactions for archived stocks. It shows sale allocations, acquisition dates and FMVs, sale proceeds, optional fees, conversion inputs, calculation lines and proposed declaration totals.

The preview and its calculation details are **not persisted**. The final tax-return fields are editable. On explicit acceptance, commit the accepted field values to the selected tax return. Do not silently write a preview or overwrite saved manual edits when recalculating. No saved preparation snapshots, revision history or tax-estimation integration are included.

Code references: [tax-return model](/Users/hadrien/Projects/eftweb/app/family/models.py:89), [tax-return detail view](/Users/hadrien/Projects/eftweb/frontend/src/views/TaxReturnDetailView.vue).

## 7. E*TRADE import changes within this scope

The current importer matches existing lots and creates sales, but ignores acquisition FMV. Extend a **new sale import** to capture the acquisition FMV used by its allocation. Updating already imported sales through a separate enrichment upload is deferred.

The reference workbook's headers have already been inspected. Only the following fields are relevant to this discussion:

| E*TRADE column(s) | Use |
| --- | --- |
| `Vest Date`, `Vest Date FMV` | RSU acquisition date and unit acquisition FMV. Match to the existing vesting using grant number plus vest date. |
| `Purchase Date Fair Mkt. Value` | Candidate for ESPP acquisition FMV. Confirm the exact column with the user at planning time if needed; the selected value must be acquisition FMV rather than discounted purchase price. |
| `Grant Date`, `Grant Number` | Keep the existing grant cross-check and source matching. Approval date remains a separate input. |
| `Acquisition Cost`, `Acquisition Cost Per Share` | Useful consistency checks against the acquisition FMV and sold quantity. They do not replace the selected FMV field. |
| `Total Proceeds`, `Proceeds Per Share`, `Date Sold`, `Order Number` | Keep the existing sale facts, grouping and proceeds cross-check. |

Do not add imports for purchase price, employee discount, grant-date FMV, ordinary income, adjusted cost basis, US qualification/election fields or wash-sale calculations. Existing purchase-date matching remains in use.

The workbook has no explicit fee or currency column. Retain USD for this import format and add an **optional fee input in the import preview**, defaulting to zero. An optional fee per grouped sale is the simplest proposal. If one broker order contains several executions, the user must be able to distribute its fee without counting it more than once. Manual sale entry gets the same optional total-fee field.

Capture FMV at source-row/lot level before grouping executions. Different source vestings or purchases can have different acquisition FMVs even when they belong to the same sale. Require repeated values for the same source lot to agree within the selected new import; do not average unrelated FMVs or change acquisition quantities.

Store acquisition FMV with the corresponding vesting or purchase. A new sale import can populate that value as part of the same transaction. If a nonzero value already differs, report the specific conflict instead of adding a reconciliation/enrichment workflow. The model location and handling of manually split allocations are implementation details for planning.

Keep preview read-only, preserve lot-quantity checks and atomic confirmation, and validate imported FMV as a finite decimal without evaluating workbook formulas. The existing ignored-row behavior remains unchanged. There is no requirement to preserve old workbook versions, hashes or receipts through this development migration beyond keeping the new import's duplicate and retry behavior correct.

Code references: [workbook parser](/Users/hadrien/Projects/eftweb/app/stocks/import_parsers.py), [matching and persistence](/Users/hadrien/Projects/eftweb/app/stocks/import_service.py), [upload API](/Users/hadrien/Projects/eftweb/app/api/stock_import.py).

## 8. Precise questions left for planning

The scope decisions in section 1 are settled. These remaining questions concern concrete inputs and behavior:

| Question | Proposed resolution or required clarification |
| --- | --- |
| Where does the RSU regime input come from? | Add shareholder approval date to the relevant grant/plan metadata, or let the user select a supported regime directly. The E*TRADE grant date is not a replacement for approval date. |
| Which column supplies ESPP acquisition FMV? | `Purchase Date Fair Mkt. Value` is present in the reference headers. Ask the user to confirm the precise column during planning if its meaning is still ambiguous. |
| How should an order-level fee be entered across executions? | Optional total fee per grouped sale, zero by default, with explicit distribution if a fee covers several executions. |
| Which date supplies the rate on a non-publication day? | Proposed: most recent published rate on or before the event date, within a short bounded lookback. Allow optional manual rate input. |
| Where does an RSU threshold excess go for a two-taxpayer return? | `1TT`/`1UT` also apply to RSU excess. Clarify attribution during planning without expanding into stock-option support. |
| What happens when a tax return already has stock-field values? | Show existing values beside proposed values and require explicit acceptance of replacement. Preserve edits during preview recalculation. |

No additional qualification evidence, acquisition-evidence review, enrichment, annual completeness or tax-estimation work is needed for the agreed scope.
