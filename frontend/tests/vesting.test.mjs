import assert from 'node:assert/strict'
import test from 'node:test'
import {
  addMonths,
  buildQuarters,
  generateVestings,
  isCalendarDate,
  summarizeGrants,
  validateGrantDetails,
  validateVestings,
} from '../src/components/stock-detail/vesting.js'

const generate = (quantity, scheduleType = 'cliff-quarterly', startDate = '2026-01-31') =>
  generateVestings({ quantity, scheduleType, startDate })
const grant = (id, rows) => ({
  id,
  title: `Grant ${id}`,
  color: '#426b5a',
  quantity: rows.reduce((sum, [, quantity]) => sum + quantity, 0),
  vestings: rows.map(([date, quantity], index) => ({ id: `${id}-${index}`, date, quantity })),
})

test('cliff schedule puts remainder shares on the final quarterly releases', () => {
  const rows = generate(1000)
  assert.equal(rows.length, 13)
  assert.equal(rows[0].date, '2027-01-31')
  assert.equal(rows[0].quantity, 250)
  assert.deepEqual(
    rows.slice(1).map((row) => row.quantity),
    [...Array(6).fill(62), ...Array(6).fill(63)],
  )
  assert.equal(rows[1].date, '2027-04-30')
  assert.equal(rows.at(-1).date, '2030-01-31')
  assert.equal(new Set(rows.map((row) => row.id)).size, 13)
})

test('quarterly schedule starts at T+15 months and finishes at T+48 months', () => {
  const rows = generate(1000, 'quarterly')
  assert.equal(rows.length, 12)
  assert.equal(rows[0].date, '2027-04-30')
  assert.equal(rows.at(-1).date, '2030-01-31')
  assert.deepEqual(
    rows.map((row) => row.quantity),
    [...Array(8).fill(83), ...Array(4).fill(84)],
  )
})

test('both schedules reconcile small and indivisible quantities and omit zero releases', () => {
  for (const schedule of ['cliff-quarterly', 'quarterly']) {
    for (let quantity = 1; quantity <= 100; quantity++) {
      const rows = generate(quantity, schedule)
      assert.equal(
        rows.reduce((sum, row) => sum + row.quantity, 0),
        quantity,
      )
      assert.ok(rows.every((row) => Number.isInteger(row.quantity) && row.quantity > 0))
      assert.equal(rows.at(-1).date, '2030-01-31')
      const quarterlyRows = rows.filter((row) => row.date !== '2027-01-31')
      for (let index = 1; index < quarterlyRows.length; index++) {
        assert.ok(quarterlyRows[index].quantity >= quarterlyRows[index - 1].quantity)
      }
    }
  }
})

test('calendar arithmetic clamps month ends without drifting subsequent releases', () => {
  assert.equal(addMonths('2024-02-29', 12), '2025-02-28')
  assert.equal(addMonths('2024-02-29', 48), '2028-02-29')
  const rows = generate(1600, 'cliff-quarterly', '2024-08-31')
  assert.equal(rows[1].date, '2025-11-30')
  assert.equal(rows[2].date, '2026-02-28')
  assert.equal(rows[3].date, '2026-05-31')
  assert.equal(rows[4].date, '2026-08-31')
  assert.equal(isCalendarDate('2025-02-29'), false)
  assert.equal(isCalendarDate('2024-02-29'), true)
  assert.equal(isCalendarDate('2026-04-31'), false)
})

test('grant and release validation rejects incomplete, fractional, and mismatched schedules', () => {
  const details = {
    title: '',
    grantDate: '2026-10-24',
    startDate: '2025-01-01',
    quantity: 100,
    scheduleType: 'quarterly',
  }
  assert.deepEqual(validateGrantDetails(details), {})
  for (const quantity of ['', 0, -1, 1.5, Number.MAX_SAFE_INTEGER + 1]) {
    assert.ok(validateGrantDetails({ ...details, quantity }).quantity)
  }
  assert.ok(validateGrantDetails({ ...details, startDate: '9999-01-01' }).startDate)
  assert.ok(validateGrantDetails({ ...details, grantDate: '2026-02-30' }).grantDate)
  assert.ok(validateVestings([], 100))
  assert.ok(validateVestings([{ date: '', quantity: 100 }], 100))
  assert.ok(validateVestings([{ date: '2027-01-01', quantity: 1.5 }], 100))
  assert.ok(validateVestings([{ date: '2027-01-01', quantity: 99 }], 100))
  assert.equal(
    validateVestings(
      [
        { date: '2027-01-01', quantity: 40 },
        { date: '2027-01-01', quantity: 60 },
      ],
      100,
    ),
    '',
  )
})

test('summaries use actual dates, include today as vested and the next-year boundary as scheduled', () => {
  const grants = [
    grant('a', [
      ['2026-10-23', 10],
      ['2026-10-24', 20],
      ['2026-10-25', 30],
      ['2027-10-24', 40],
      ['2027-10-25', 50],
    ]),
    grant('b', [['2026-10-25', 15]]),
  ]
  assert.deepEqual(summarizeGrants(grants, '2026-10-24'), {
    awarded: 165,
    vested: 30,
    unvested: 135,
    nextTwelveMonths: 85,
    nextRelease: { date: '2026-10-25', quantity: 45 },
  })
  assert.equal(summarizeGrants(grants, '2028-01-01').nextRelease, null)
  assert.deepEqual(summarizeGrants([], '2026-10-24'), {
    awarded: 0,
    vested: 0,
    unvested: 0,
    nextTwelveMonths: 0,
    nextRelease: null,
  })
})

test('quarters aggregate grants while retaining exact dates and mixed vesting status', () => {
  const grants = [
    grant('a', [
      ['2026-10-01', 10],
      ['2026-12-01', 20],
      ['2027-07-01', 30],
    ]),
    grant('b', [['2026-12-01', 40]]),
  ]
  const quarters = buildQuarters(grants, '2026-10-24')
  assert.deepEqual(
    quarters.map((quarter) => quarter.id),
    ['2026-Q4', '2027-Q1', '2027-Q2', '2027-Q3'],
  )
  assert.equal(quarters[0].vested, 10)
  assert.equal(quarters[0].scheduled, 60)
  assert.equal(quarters[0].total, 70)
  assert.equal(quarters[0].segments.length, 3)
  assert.equal(quarters[0].releases.length, 3)
  assert.equal(quarters[1].total, 0)
  assert.equal(quarters[3].total, 30)
  assert.deepEqual(buildQuarters([], '2026-10-24'), [])
})

test('timeline includes today when all releases are in the past or future', () => {
  assert.equal(buildQuarters([grant('a', [['2020-01-01', 10]])], '2026-10-24').at(-1).id, '2026-Q4')
  assert.equal(buildQuarters([grant('b', [['2030-01-01', 10]])], '2026-10-24')[0].id, '2026-Q4')
})
