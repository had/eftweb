import { isCalendarDate, isWholeQuantity } from './vesting.js'
import { acquisitionLots, allocationKey } from './acquisitions.js'

// Use integer millionths for exact decimal input and gross proceeds calculation.
export function priceMicros(value) {
  const text = String(value ?? '').trim()
  if (!/^\d{1,8}(\.\d{1,6})?$/.test(text)) return null
  const [whole, fraction = ''] = text.split('.')
  const micros = BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, '0'))
  return micros > 0n ? micros : null
}

export function saleProceeds(quantity, price) {
  const micros = priceMicros(price)
  if (!isWholeQuantity(quantity) || micros === null) return null
  const cents = (BigInt(quantity) * micros + 5000n) / 10000n
  const dollars = cents / 100n
  return `$${new Intl.NumberFormat('en-US').format(dollars)}.${String(cents % 100n).padStart(2, '0')}`
}

export function availablePockets(grants, sales, transactionDate, purchases = []) {
  const used = new Map()
  for (const sale of sales)
    for (const allocation of sale.allocations)
      used.set(
        allocationKey(allocation),
        (used.get(allocationKey(allocation)) || 0) + allocation.quantity,
      )
  return acquisitionLots(grants, purchases)
    .map((lot) => ({
      ...lot,
      grantTitle: lot.title,
      remaining: lot.quantity - (used.get(lot.key) || 0),
    }))
    .filter((pocket) => pocket.date <= transactionDate && pocket.remaining > 0)
}

export function validateSale(draft, pockets, today) {
  const errors = {}
  if (!isCalendarDate(draft.transactionDate) || draft.transactionDate > today)
    errors.transactionDate = 'Enter a valid transaction date, today or earlier.'
  if (!isWholeQuantity(draft.quantity)) errors.quantity = 'Enter a positive whole number of shares.'
  if (priceMicros(draft.proceedsPerShare) === null)
    errors.proceedsPerShare =
      'Enter a positive USD amount below 100,000,000, with at most six decimals.'
  let total = 0
  const seen = new Set()
  for (const allocation of draft.allocations) {
    const key = allocationKey(allocation)
    const pocket = pockets.find((row) => row.key === key)
    if (
      seen.has(key) ||
      (allocation.vestingId !== undefined && allocation.purchaseId !== undefined) ||
      !pocket ||
      !isWholeQuantity(allocation.quantity) ||
      Number(allocation.quantity) > pocket.remaining
    )
      errors.allocations = 'Use positive whole quantities within each lot’s available shares.'
    seen.add(key)
    total += Number(allocation.quantity)
  }
  if (!draft.allocations.length || total !== Number(draft.quantity))
    errors.allocations ||= 'Allocated shares must exactly match the sale quantity.'
  return errors
}

export function buildHoldings(grants, sales, today, purchases = []) {
  const pockets = new Map()
  const events = []
  for (const lot of acquisitionLots(grants, purchases)) {
    pockets.set(lot.key, { grantTitle: lot.title, date: lot.date })
    if (lot.date <= today)
      events.push({
        id: lot.key.replace(':', '-'),
        order: lot.id,
        date: lot.date,
        type: lot.type,
        label: lot.type === 'purchase' ? 'Purchase' : 'Vesting',
        grantTitle: lot.title,
        change: lot.quantity,
      })
  }
  for (const sale of sales) {
    if (sale.transactionDate > today) continue
    events.push({
      id: `sale-${sale.id}`,
      order: sale.id,
      date: sale.transactionDate,
      type: 'sale',
      label: 'Sale',
      change: -sale.quantity,
      sale,
      proceeds: saleProceeds(sale.quantity, sale.proceedsPerShare),
      allocations: sale.allocations.map((allocation) => ({
        ...allocation,
        key: allocationKey(allocation),
        ...pockets.get(allocationKey(allocation)),
      })),
    })
  }
  events.sort(
    (a, b) =>
      a.date.localeCompare(b.date) ||
      Number(a.type === 'sale') - Number(b.type === 'sale') ||
      a.type.localeCompare(b.type) ||
      a.order - b.order,
  )
  let balance = 0,
    vested = 0,
    acquired = 0,
    sold = 0
  for (const event of events) {
    balance += event.change
    event.balance = balance
    if (event.type === 'sale') sold -= event.change
    else acquired += event.change
    if (event.type === 'vesting') vested += event.change
  }
  return { events, vested, acquired, sold, held: balance }
}
