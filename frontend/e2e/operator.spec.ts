import { test, expect } from '@playwright/test';

test('operator sees twelve honest anchors and the persisted labelled fixture', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(process.env.TRAFFIC_BROWSER_URL || 'http://localhost:5173', { waitUntil: 'domcontentloaded' });
  await expect(page.getByText(/12 configured anchors/)).toBeVisible({ timeout: 30000 });
  await expect(page.locator('.leaflet-interactive')).toHaveCount(12);
  const points = await page.request.get(`${new URL(page.url()).origin}/api/monitoring/points`);
  expect(points.ok()).toBeTruthy();
  const rows = await points.json();
  expect(rows).toHaveLength(12);
  expect(rows.find((row: { road_id: string }) => row.road_id === 'HN_HK_001').source).toBe('acceptance-fixture');
  // Each SVG marker is a configured anchor; no invented road polyline is rendered.
  expect(rows.every((row: { geometry: unknown }) => row.geometry === null)).toBeTruthy();
  expect(errors).toEqual([]);
});

test('an HCMC anchor selected from All keeps its city and supported horizons', async ({ page }) => {
  await page.goto(process.env.TRAFFIC_BROWSER_URL || 'http://localhost:5173', { waitUntil: 'domcontentloaded' });
  await expect(page.getByText(/12 configured anchors/)).toBeVisible({ timeout: 30000 });
  const response = await page.request.get(`${new URL(page.url()).origin}/api/monitoring/points`);
  const points: { road_id: string; city: string }[] = await response.json();
  const index = points.reduce((last, point, position) => point.city === 'hcmc' ? position : last, -1);
  expect(index).toBeGreaterThanOrEqual(0);
  await page.locator('.leaflet-interactive').nth(index).click();
  const popup = page.locator('.leaflet-popup-content');
  const selected = await popup.locator('strong').innerText();
  expect(selected).toMatch(/^HCMC_/);
  await popup.getByRole('button', { name: 'View forecast' }).click();
  await expect(page).toHaveURL(/city=hcmc/);
  await expect(page.locator('select')).toHaveValue(selected);
  await expect(page.locator('select option')).toHaveCount(6);
  await expect(page.getByText('15 minute P50', { exact: true })).toBeVisible();
  await expect(page.getByText('60 minute P50', { exact: true })).toBeVisible();
  await expect(page.getByText('240 minute P50', { exact: true })).toHaveCount(0);
});
