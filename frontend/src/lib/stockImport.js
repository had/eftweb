export const lotKey = (allocation) =>
  allocation.vesting_id !== undefined
    ? `vesting_id:${allocation.vesting_id}`
    : `purchase_id:${allocation.purchase_id}`

export function editedAllocations(rows) {
  return rows.map((row) => {
    const [source, id] = row.lot.split(':')
    return { [source]: Number(id), quantity: Number(row.quantity) }
  })
}

const signature = (allocations) =>
  JSON.stringify(allocations.map((row) => [lotKey(row), row.quantity]).sort())

export function saleDecision(sale, draft) {
  const allocations = editedAllocations(draft.allocations)
  return {
    skip: draft.skip,
    reviewed: draft.reviewed,
    ...(signature(allocations) !== signature(sale.allocations) ? { allocations } : {}),
  }
}

export function importIssues(preview, drafts) {
  if (!preview) return ['Choose a file and preview it first.']
  const issues = [...preview.errors]
  if (preview.format === 'eftweb') return issues
  const available = new Map(preview.lots.map((lot) => [`${lot.source}:${lot.id}`, lot.available]))
  let selected = 0
  for (const sale of preview.sales) {
    const draft = drafts[sale.key]
    if (!draft || draft.skip || sale.status === 'duplicate') continue
    selected += 1
    if (['invalid', 'conflict'].includes(sale.status)) {
      issues.push('Skip unsupported or conflicting sales before importing.')
      continue
    }
    const decision = saleDecision(sale, draft)
    if (
      (decision.allocations ||
        sale.warnings.length ||
        sale.matching_issues?.length ||
        sale.possible_duplicate_ids?.length) &&
      !draft.reviewed
    )
      issues.push('Confirm that you reviewed each flagged or edited sale.')
    const seen = new Set()
    let quantity = 0
    const allocatedByType = { vesting_id: 0, purchase_id: 0 }
    for (const row of draft.allocations) {
      const lot = preview.lots.find((lot) => `${lot.source}:${lot.id}` === row.lot)
      const shares = Number(row.quantity)
      if (
        !lot ||
        seen.has(row.lot) ||
        !Number.isSafeInteger(shares) ||
        shares <= 0 ||
        lot.date > sale.transaction_date
      ) {
        issues.push('Choose distinct acquired lots and positive whole-share quantities.')
        continue
      }
      seen.add(row.lot)
      quantity += shares
      allocatedByType[lot.source] += shares
      available.set(row.lot, available.get(row.lot) - shares)
      if (available.get(row.lot) < 0)
        issues.push('Selected sales exceed an acquisition lot’s available shares.')
    }
    if (quantity !== sale.quantity) issues.push('Allocations must equal each sale’s quantity.')
    for (const [type, source] of [
      ['RS', 'vesting_id'],
      ['ESPP', 'purchase_id'],
    ]) {
      const expected = sale.sources
        .filter((lot) => lot.plan_type === type)
        .reduce((sum, lot) => sum + lot.quantity, 0)
      if (allocatedByType[source] !== expected)
        issues.push('Allocations must preserve the RSU and ESPP share quantities.')
    }
  }
  if (!selected) issues.push('No new sales selected for import.')
  return [...new Set(issues)]
}
