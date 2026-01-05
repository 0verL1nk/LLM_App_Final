import { test, expect } from '@playwright/test';
import path from 'path';

test.describe('Document Management Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Login before each test
    await page.goto('/login');
    await page.fill('input[name="username"]', 'testuser');
    await page.fill('input[name="password"]', 'password123');
    await page.click('button[type="submit"]');
  });

  test('should navigate to documents list and show empty state or files', async ({ page }) => {
    await page.click('a:has-text("文献中心")');
    await expect(page).toHaveURL('/documents');
    await expect(page.locator('h1')).toContainText('文献列表');
  });

  test('should open workspace for a document', async ({ page }) => {
    await page.goto('/documents');
    
    // Check if there's a view button and click it
    const viewButton = page.locator('a[title="查看详情"]').first();
    if (await viewButton.isVisible()) {
      await viewButton.click();
      await expect(page).toHaveURL(/\/documents\/\d+/);
      await expect(page.locator('span:has-text("PDF")')).toBeVisible();
    }
  });

  test('should toggle AI tools in workspace', async ({ page }) => {
    // Navigate to a mock document
    await page.goto('/documents/1');
    
    // Check AI tabs
    const qaTab = page.locator('button:has-text("AI 问答")');
    await qaTab.click();
    await expect(page.locator('span:has-text("文献智能问答")')).toBeVisible();
    
    const mindmapTab = page.locator('button:has-text("思维导图")');
    await mindmapTab.click();
    await expect(page.locator('span:has-text("结构化思维导图")')).toBeVisible();
  });
});
