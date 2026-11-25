import { expect, test } from '@playwright/test'

const PAGES = ['/', '/calculators', '/cable-library', '/comparison', '/validation', '/resources', '/settings', '/about', '/contact', '/privacy', '/terms', '/disclaimer']

function watchErrors(page) {
  const errs = []
  page.on('pageerror', (e) => errs.push(String(e)))
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()) })
  return errs
}

test('every public page renders without errors and with its own title', async ({ page }) => {
  const errs = watchErrors(page)
  for (const p of PAGES) {
    await page.goto(p)
    await expect(page.locator('.topbar-logo')).toBeVisible()
    await expect(page.locator('h1').first()).toBeVisible()
    expect(await page.title()).toContain('Cable-N')
  }
  expect(await page.content()).not.toContain('Elsewedy')
  expect(errs).toEqual([])
})

test('single feeder: steps, calculate, results, save, reload saved', async ({ page }) => {
  const errs = watchErrors(page)
  await page.goto('/calculators/single-feeder')
  for (let i = 0; i < 4; i++) await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Calculate', exact: true }).click()
  await expect(page.getByText('Recommended single run')).toBeVisible()
  await expect(page.getByText('Ampacity (Ib <= Iz)')).toBeVisible()
  for (const t of ['All options', 'Correction factors', 'Installation diagram', 'Warnings & basis']) {
    await page.getByRole('tab', { name: new RegExp(t) }).click()
  }
  await page.screenshot({ path: 'e2e-out/single-feeder.png', fullPage: true })
  await page.getByRole('button', { name: /Save to browser/ }).click()
  await page.getByPlaceholder('e.g. Pump P-101 feeder').fill('E2E feeder')
  await page.getByRole('dialog').getByRole('button', { name: /^Save$/ }).click()
  await expect(page.getByText(/Saved “E2E feeder”/)).toBeVisible()
  // change input -> outdated
  await page.getByRole('button', { name: /Electrical system/ }).click()
  await page.locator('input[type=number]').nth(1).fill('3')
  await expect(page.getByText(/OUTDATED/)).toBeVisible()
  await page.goto('/calculators?tab=saved')
  await page.getByRole('link', { name: 'E2E feeder' }).click()
  await expect(page.getByText('Recommended single run')).toBeVisible()
  expect(errs).toEqual([])
})

test('single feeder PDF and Excel downloads', async ({ page }) => {
  await page.goto('/calculators/single-feeder')
  for (let i = 0; i < 4; i++) await page.getByRole('button', { name: 'Continue' }).click()
  await page.getByRole('button', { name: 'Calculate', exact: true }).click()
  await expect(page.getByText('Recommended single run')).toBeVisible()
  const [x] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: /Excel/ }).click()])
  expect(x.suggestedFilename()).toMatch(/\.xlsx$/)
  await page.getByRole('button', { name: /PDF report/ }).click()
  const [pdf] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: /Generate PDF/ }).click()])
  expect(pdf.suggestedFilename()).toMatch(/\.pdf$/)
})

test('batch schedule with progress', async ({ page }) => {
  const errs = watchErrors(page)
  await page.goto('/calculators/batch')
  await page.getByRole('button', { name: /Add feeder/ }).click()
  await page.getByRole('button', { name: /Calculate schedule/ }).click()
  await expect(page.getByRole('heading', { name: 'Cable schedule' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('Feeders entered')).toBeVisible()
  await page.screenshot({ path: 'e2e-out/batch.png', fullPage: true })
  expect(errs).toEqual([])
})

test('current rating verification', async ({ page }) => {
  const errs = watchErrors(page)
  await page.goto('/calculators/current-rating')
  await page.getByRole('button', { name: /Calculate ratings/ }).click()
  await expect(page.getByText('Lowest rating')).toBeVisible()
  await page.screenshot({ path: 'e2e-out/current-rating.png', fullPage: true })
  expect(errs).toEqual([])
})

test('advanced MV/HV analysis and tabs', async ({ page }) => {
  const errs = watchErrors(page)
  await page.goto('/calculators/advanced-mv-hv')
  await expect(page.getByText('T1 / T2 / T3')).toBeVisible()
  await page.getByRole('button', { name: /Run full analysis/ }).click()
  await expect(page.getByText('Governing rating')).toBeVisible()
  for (const t of ['Current ratings', 'Electrical', 'Sequence', 'Thermal', 'Losses', 'Installation layout', 'Short circuit', 'Cable data', 'Assumptions', 'Calculation details']) {
    await page.getByRole('tab', { name: new RegExp(t) }).click()
  }
  await page.screenshot({ path: 'e2e-out/advanced.png', fullPage: true })
  expect(errs).toEqual([])
})

test('validation case runs', async ({ page }) => {
  await page.goto('/validation')
  await page.getByRole('row', { name: /reference workbook/ }).first().getByRole('button', { name: 'Run' }).click()
  await expect(page.getByText('Pass', { exact: false }).first()).toBeVisible({ timeout: 30_000 })
})

test('mobile layout and menu', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Menu' }).click()
  await page.getByRole('link', { name: /Engineering Resources/ }).click()
  await expect(page).toHaveURL(/resources/)
  await page.screenshot({ path: 'e2e-out/mobile.png', fullPage: false })
})

test('accent colour changes brand but not status colours', async ({ page }) => {
  await page.goto('/settings')
  await page.getByRole('button', { name: 'Ocean Blue' }).click()
  const brand = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--brand-red').trim())
  const pass = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--pass').trim())
  expect(brand).toBe('#1d4ed8')
  expect(pass).toBe('#1e7a34')
  await page.getByRole('button', { name: 'Cable-N Red' }).click()
})
