const { test, expect } = require('@playwright/test');

test('localhost smoke', async ({ page }) => {
  await page.goto('http://localhost:5173/analytika', { waitUntil: 'networkidle' });
  await expect(page.locator('body')).toContainText('Nabídka podle kraje');
  await expect(page.locator('body')).not.toContainText('Error');
  await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' });
  await expect(page.locator('body')).toContainText('Přehled trhu');
});
