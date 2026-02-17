import { test, expect } from '@playwright/test';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:5174';

test('chat page loads correctly', async ({ page }) => {
  await page.goto(BASE_URL);
  
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
  await page.goto(BASE_URL);
  
  const input = page.locator('textarea');
  await input.fill('Test question');
  
  await expect(input).toHaveValue('Test question');
});

test('send button is disabled when input is empty', async ({ page }) => {
  await page.goto(BASE_URL);
  
  const sendButton = page.locator('button:has-text("Send")');
  await expect(sendButton).toBeDisabled();
});
