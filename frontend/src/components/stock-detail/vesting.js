import { formatNumber } from '../../lib/numberFormat.js'

import { acquisitionLots, acquisitionPlans } from './acquisitions.js'

export const SCHEDULES = [
  {
    value: 'quarterly',
    label: 'Quarterly after year one',
    description:
      'Nothing in the first year or at its anniversary. Then 1/12 every three months from T + 15 to T + 48 months. Whole-share remainders go to the final releases.',
  },
  {
    value: 'cliff-quarterly',
    label: '25% cliff + quarterly',
    description:
      '25% at T + 12 months, then 1/16 every three months from T + 15 to T + 48 months. Whole-share remainders go to the final releases.',
  },
]

const colors = [
  '#426b5a',
  '#386f88',
  '#986b56',
  '#76688a',
  '#ad843c',
  '#337b78',
  '#a45472',
  '#667538',
]
export const grantColor = (index) => colors[index % colors.length]
export const createId = () => crypto.randomUUID()

export const localDate = (date = new Date()) =>
  [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, '0'),
    String(date.getDate()).padStart(2, '0'),
  ].join('-')

export function isCalendarDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000'))
    return false
  const date = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value
}

// Always calculate from the reference date, never from the previous release.
export function addMonths(value, months) {
  if (!isCalendarDate(value)) return ''
  const [year, month, day] = value.split('-').map(Number)
  const totalMonths = year * 12 + month - 1 + months
  const targetYear = Math.floor(totalMonths / 12)
  if (targetYear < 1 || targetYear > 9999) return ''
  const targetMonth = totalMonths % 12
  const lastDay = new Date(0)
  lastDay.setUTCFullYear(targetYear, targetMonth + 1, 0)
  return `${String(targetYear).padStart(4, '0')}-${String(targetMonth + 1).padStart(2, '0')}-${String(Math.min(day, lastDay.getUTCDate())).padStart(2, '0')}`
}

export const isWholeQuantity = (value) =>
  (typeof value === 'string' || typeof value === 'number') &&
  value !== '' &&
  Number.isSafeInteger(Number(value)) &&
  Number(value) > 0

export function validateGrantDetails(details) {
  const errors = {}
  if (!isCalendarDate(details.grantDate)) errors.grantDate = 'Enter a valid grant date.'
  if (!isWholeQuantity(details.quantity))
    errors.quantity = 'Enter a positive whole number of shares.'
  if (!isCalendarDate(details.startDate) || !addMonths(details.startDate, 48))
    errors.startDate = 'Enter a valid reference date allowing a four-year schedule.'
  if (!SCHEDULES.some((schedule) => schedule.value === details.scheduleType))
    errors.scheduleType = 'Choose a vesting schedule.'
  if (details.title.trim().length > 256) errors.title = 'Use a title of at most 256 characters.'
  return errors
}

export function generateVestings({ quantity, startDate, scheduleType }) {
  const count = Number(quantity)
  if (
    !isWholeQuantity(quantity) ||
    !isCalendarDate(startDate) ||
    !addMonths(startDate, 48) ||
    !SCHEDULES.some((item) => item.value === scheduleType)
  ) {
    throw new Error('Invalid vesting schedule parameters')
  }
  const cliff = scheduleType === 'cliff-quarterly' ? Math.floor(count / 4) : 0
  const base = Math.floor(count / (scheduleType === 'cliff-quarterly' ? 16 : 12))
  const remainder = count - cliff - base * 12
  const releases = scheduleType === 'cliff-quarterly' ? [{ months: 12, quantity: cliff }] : []
  for (let index = 0; index < 12; index++) {
    releases.push({ months: 15 + index * 3, quantity: base + (index >= 12 - remainder ? 1 : 0) })
  }
  return releases
    .filter((release) => release.quantity > 0)
    .map((release) => ({
      id: createId(),
      date: addMonths(startDate, release.months),
      quantity: release.quantity,
    }))
}

export const scheduledTotal = (vestings) =>
  vestings.reduce((sum, release) => sum + (Number(release.quantity) || 0), 0)

export function validateVestings(vestings, quantity) {
  if (!vestings.length) return 'Add at least one vesting release.'
  if (vestings.some((release) => !isCalendarDate(release.date)))
    return 'Enter a valid date for every release.'
  if (vestings.some((release) => !isWholeQuantity(release.quantity)))
    return 'Every release must have a positive whole number of shares.'
  if (scheduledTotal(vestings) !== Number(quantity))
    return 'Scheduled shares must exactly match the granted quantity.'
  return ''
}

export function summarizeGrants(grants, today) {
  const releases = grants.flatMap((grant) => grant.vestings)
  const awarded = grants.reduce((sum, grant) => sum + grant.quantity, 0)
  const vested = releases
    .filter((release) => release.date <= today)
    .reduce((sum, release) => sum + release.quantity, 0)
  const horizon = addMonths(today, 12)
  const upcoming = releases
    .filter((release) => release.date > today)
    .sort((a, b) => a.date.localeCompare(b.date))
  const nextDate = upcoming[0]?.date
  return {
    awarded,
    vested,
    unvested: awarded - vested,
    nextTwelveMonths: upcoming
      .filter((release) => release.date <= horizon)
      .reduce((sum, release) => sum + release.quantity, 0),
    nextRelease: nextDate
      ? {
          date: nextDate,
          quantity: upcoming
            .filter((release) => release.date === nextDate)
            .reduce((sum, release) => sum + release.quantity, 0),
        }
      : null,
  }
}

const quarterIndex = (date) =>
  Number(date.slice(0, 4)) * 4 + Math.floor((Number(date.slice(5, 7)) - 1) / 3)

export function summarizePortfolio(grants, purchases, today) {
  const summary = summarizeGrants(grants, today)
  const purchased = (purchases || [])
    .filter((purchase) => purchase.purchaseDate <= today)
    .reduce((sum, purchase) => sum + purchase.quantity, 0)
  return { ...summary, total: summary.awarded + purchased, acquired: summary.vested + purchased }
}

export function validatePurchase(details, today) {
  const errors = {}
  if (!isCalendarDate(details.purchaseDate) || details.purchaseDate > today)
    errors.purchaseDate = 'Enter a valid purchase date, today or earlier.'
  if (!isWholeQuantity(details.quantity))
    errors.quantity = 'Enter a positive whole number of shares.'
  return errors
}

export function buildQuarters(grants, today, purchases = []) {
  const releases = acquisitionLots(grants, purchases).map((lot) => ({
    ...lot,
    scheduled: lot.date > today,
  }))
  if (!releases.length) return []
  const plans = acquisitionPlans(grants, purchases)
  const indices = [quarterIndex(today), ...releases.map((release) => quarterIndex(release.date))]
  const first = Math.min(...indices)
  const last = Math.max(...indices)
  const buckets = Array.from({ length: last - first + 1 }, (_, offset) => {
    const index = first + offset
    const year = Math.floor(index / 4)
    const quarter = (index % 4) + 1
    return {
      id: `${String(year).padStart(4, '0')}-Q${quarter}`,
      year,
      quarter: `Q${quarter}`,
      index,
      releases: [],
      segments: [],
      total: 0,
      vested: 0,
      scheduled: 0,
    }
  })
  for (const release of releases) buckets[quarterIndex(release.date) - first].releases.push(release)
  for (const bucket of buckets) {
    bucket.releases.sort((a, b) => a.date.localeCompare(b.date))
    for (const plan of plans) {
      for (const scheduled of [false, true]) {
        const quantity = bucket.releases
          .filter((release) => release.planKey === plan.key && release.scheduled === scheduled)
          .reduce((sum, release) => sum + release.quantity, 0)
        if (quantity)
          bucket.segments.push({
            id: `${plan.key}-${scheduled}`,
            quantity,
            color: plan.color,
            scheduled,
          })
        bucket[scheduled ? 'scheduled' : 'vested'] += quantity
      }
    }
    bucket.total = bucket.vested + bucket.scheduled
  }
  return buckets
}

export const formatShares = formatNumber
export const formatDate = (value) =>
  new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`))
