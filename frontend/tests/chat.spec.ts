import { test, expect } from '@playwright/test';

test('chat page loads correctly', async ({ page }) => {
  await page.goto('/');
  
  // Check page title
  await expect(page).toHaveTitle(/Health Screening Q&A/);
  
  // Check header
  await expect(page.locator('h1')).toContainText('Health Screening Q&A');
  
  // Check welcome message
  await expect(page.locator('.welcome')).toContainText('health screening results');
  
  // Check input area exists
  await expect(page.locator('textarea')).toBeVisible();
  await expect(page.locator('button:has-text("Send")')).toBeVisible();
  
  // Check New Chat button
  await expect(page.locator('button:has-text("New Chat")')).toBeVisible();
});

test('can type in input field', async ({ page }) => {
  await page.goto('/');
  
  const input = page.locator('textarea');
  await input.click();
  await input.pressSequentially('Test question');
  await page.waitForTimeout(300);
  
  await expect(input).toHaveValue('Test question');
});

test('send button is disabled when input is empty', async ({ page }) => {
  await page.goto('/');
  
  const sendButton = page.locator('button:has-text("Send")');
  await expect(sendButton).toBeDisabled();
});
