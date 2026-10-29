import { isCalendarDate, isWholeQuantity } from './vesting.js'

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

export function availablePockets(grants, sales, transactionDate) {
  const used = new Map()
  for (const sale of sales)
    for (const allocation of sale.allocations)
      used.set(allocation.vestingId, (used.get(allocation.vestingId) || 0) + allocation.quantity)
  return grants
    .flatMap((grant) =>
      grant.vestings.map((release) => ({
        ...release,
        grantId: grant.id,
        grantTitle: grant.title,
        color: grant.color,
        remaining: release.quantity - (used.get(release.id) || 0),
      })),
    )
    .filter((pocket) => pocket.date <= transactionDate && pocket.remaining > 0)
    .sort((a, b) => a.date.localeCompare(b.date) || a.grantId - b.grantId || a.id - b.id)
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
    const pocket = pockets.find((row) => row.id === allocation.vestingId)
    if (
      seen.has(allocation.vestingId) ||
      !pocket ||
      !isWholeQuantity(allocation.quantity) ||
      Number(allocation.quantity) > pocket.remaining
    )
      errors.allocations = 'Use positive whole quantities within each pocket’s available shares.'
    seen.add(allocation.vestingId)
    total += Number(allocation.quantity)
  }
  if (!draft.allocations.length || total !== Number(draft.quantity))
    errors.allocations ||= 'Allocated shares must exactly match the sale quantity.'
  return errors
}

export function buildHoldings(grants, sales, today) {
  const pockets = new Map()
  const events = []
  for (const grant of grants) {
    for (const release of grant.vestings) {
      pockets.set(release.id, { grantTitle: grant.title, date: release.date })
      if (release.date <= today)
        events.push({
          id: `vesting-${release.id}`,
          order: release.id,
          date: release.date,
          type: 'vesting',
          label: 'Vesting',
          grantTitle: grant.title,
          change: release.quantity,
        })
    }
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
        ...pockets.get(allocation.vestingId),
      })),
    })
  }
  events.sort(
    (a, b) =>
      a.date.localeCompare(b.date) ||
      (a.type === b.type ? a.order - b.order : a.type === 'vesting' ? -1 : 1),
  )
  let balance = 0,
    vested = 0,
    sold = 0
  for (const event of events) {
    balance += event.change
    event.balance = balance
    if (event.type === 'vesting') vested += event.change
    else sold -= event.change
  }
  return { events, vested, sold, held: balance }
}
