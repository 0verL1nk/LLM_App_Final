import { test, expect } from '@playwright/test';

test.describe('Authentication Flow', () => {
  test('should allow user to login and redirect to dashboard', async ({ page }) => {
    await page.goto('/login');
    
    // Fill login form
    await page.fill('input[name="username"]', 'testuser');
    await page.fill('input[name="password"]', 'password123');
    
    // Submit
    await page.click('button[type="submit"]');
    
    // Verify redirection to dashboard
    await expect(page).toHaveURL('/');
    await expect(page.locator('h1')).toContainText('下午好, testuser');
  });

  test('should allow user to toggle theme', async ({ page }) => {
    await page.goto('/login');
    await page.fill('input[name="username"]', 'testuser');
    await page.fill('input[name="password"]', 'password123');
    await page.click('button[type="submit"]');

    const themeToggle = page.locator('button[aria-label="Toggle theme"]');
    await expect(page.locator('html')).not.toHaveClass(/dark/);
    
    await themeToggle.click();
    await expect(page.locator('html')).toHaveClass(/dark/);
  });
});
