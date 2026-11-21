// Purchases remain separate records; this projection lets all acquisition views share lots.
export const purchaseColor = '#b86727'
export const allocationKey = (allocation) =>
  allocation.purchaseId !== undefined
    ? `purchase:${allocation.purchaseId}`
    : `vesting:${allocation.vestingId}`

export function acquisitionLots(grants = [], purchases = []) {
  return [
    ...grants.flatMap((grant) =>
      grant.vestings.map((release) => ({
        ...release,
        key: `vesting:${release.id}`,
        type: 'vesting',
        vestingId: release.id,
        grantId: grant.id,
        planKey: `grant:${grant.id}`,
        title: grant.title,
        color: grant.color,
      })),
    ),
    ...purchases.map((purchase) => ({
      id: purchase.id,
      key: `purchase:${purchase.id}`,
      type: 'purchase',
      purchaseId: purchase.id,
      planKey: `purchase-plan:${purchase.planName}`,
      title: purchase.planName,
      date: purchase.purchaseDate,
      quantity: purchase.quantity,
      acquisition_fmv: purchase.acquisition_fmv,
      color: purchaseColor,
    })),
  ].sort(
    (a, b) => a.date.localeCompare(b.date) || a.key.localeCompare(b.key, 'en', { numeric: true }),
  )
}

export function acquisitionPlans(grants = [], purchases = []) {
  return [
    ...grants.map((grant) => ({
      key: `grant:${grant.id}`,
      title: grant.title,
      color: grant.color,
    })),
    ...[...new Set(purchases.map((purchase) => purchase.planName))].map((title) => ({
      key: `purchase-plan:${title}`,
      title,
      color: purchaseColor,
    })),
  ]
}
