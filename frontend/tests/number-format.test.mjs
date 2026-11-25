import assert from 'node:assert/strict'
import test from 'node:test'
import { computed } from 'vue'
import {
  DEFAULT_NUMBER_LOCALE,
  NUMBER_LOCALES,
  formatCurrency,
  formatDecimal,
  formatNumber,
  formatPercent,
  numberLocale,
} from '../src/lib/numberFormat.js'
import { formatShares } from '../src/components/stock-detail/vesting.js'
import { saleProceeds, buildHoldings } from '../src/components/stock-detail/sales.js'
import { formatStockValue } from '../src/lib/stockQuotes.js'

for (const { id } of NUMBER_LOCALES) {
  test(`${id} formats numbers, currencies, percentages and exact stock values consistently`, (t) => {
    t.after(() => {
      numberLocale.value = DEFAULT_NUMBER_LOCALE
    })
    numberLocale.value = id
    assert.equal(formatNumber(1234567.89), new Intl.NumberFormat(id).format(1234567.89))
    assert.equal(formatShares(12345), new Intl.NumberFormat(id).format(12345))
    assert.equal(
      formatCurrency(1234.56),
      new Intl.NumberFormat(id, { style: 'currency', currency: 'EUR' }).format(1234.56),
    )
    assert.equal(
      formatPercent(0.125),
      new Intl.NumberFormat(id, { style: 'percent', maximumFractionDigits: 1 }).format(0.125),
    )
    const usd = new Intl.NumberFormat(id, {
      style: 'currency',
      currency: 'USD',
      currencyDisplay: 'narrowSymbol',
    })
    assert.equal(formatStockValue(99, '19.99'), usd.format(1979.01))
    assert.equal(formatStockValue(0, '19.99'), usd.format(0))
    assert.equal(saleProceeds(40, '123.456789'), usd.format(4938.27))
    const exact = usd
      .formatToParts(9097271247288400n)
      .map((part) => (part.type === 'fraction' ? '91' : part.value))
      .join('')
    assert.equal(formatStockValue(Number.MAX_SAFE_INTEGER, '1.01'), exact)
    assert.equal(
      formatDecimal('1234.560000'),
      new Intl.NumberFormat(id, { minimumFractionDigits: 6 }).format(1234.56),
    )
  })
}

test('changing the locale invalidates existing computed displays and ledger proceeds', (t) => {
  t.after(() => {
    numberLocale.value = DEFAULT_NUMBER_LOCALE
  })
  numberLocale.value = 'en-GB'
  const shares = computed(() => formatShares(1234))
  const amount = computed(() => formatCurrency(1234.56))
  const holdings = computed(() =>
    buildHoldings(
      [],
      [
        {
          id: 1,
          transactionDate: '2026-01-01',
          quantity: 99,
          proceedsPerShare: '19.99',
          allocations: [],
        },
      ],
      '2026-11-25',
    ),
  )
  assert.equal(shares.value, '1,234')
  assert.equal(amount.value, '€1,234.56')
  assert.equal(holdings.value.events[0].proceeds, '$1,979.01')
  numberLocale.value = 'fr-FR'
  assert.equal(shares.value, '1\u202f234')
  assert.equal(amount.value, '1\u202f234,56\u00a0€')
  assert.equal(holdings.value.events[0].proceeds, '1\u202f979,01\u00a0$')
  assert.equal(formatNumber(null), '—')
  assert.equal(formatCurrency(undefined), '—')
  assert.equal(formatPercent(null), '—')
})
