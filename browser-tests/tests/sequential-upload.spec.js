const path = require('path');
const { expect, test } = require('@playwright/test');

function isAudioUpload(request) {
  return request.method() === 'POST' && /\/store\/books\/[^/]+\/audio\/upload\/$/.test(request.url());
}

async function removeBookIfPresent(page, title) {
  const heading = page.getByRole('heading', { name: title, exact: true });
  if (!(await heading.isVisible().catch(() => false))) {
    await page.goto(`/store/books/?query=${encodeURIComponent(title)}`);
    const bookLink = page.getByRole('link', { name: title, exact: true });
    if ((await bookLink.count()) === 0) return;
    await bookLink.click();
  }

  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', { name: /remove/i }).click();
  await expect(page).toHaveURL(/\/store\/books\/$/);
}

test('uploads every selected audio file and redirects to the book', async ({ page }) => {
  const title = `Browser upload ${Date.now()}`;
  const uploadEvents = [];
  let testFailed = false;
  page.on('request', request => {
    if (isAudioUpload(request)) uploadEvents.push('request');
  });
  page.on('response', response => {
    if (isAudioUpload(response.request())) uploadEvents.push('response');
  });

  await page.goto('/auth/login/');
  await page.locator('[name="username"]').fill(process.env.TEST_ADMIN_USERNAME || 'admin');
  await page.locator('[name="password"]').fill(process.env.TEST_ADMIN_PASSWORD || 'admin');
  await page.getByRole('button', { name: 'Login' }).click();

  await page.goto('/store/book/add/');
  await page.locator('[name="title"]').fill(title);
  await page.locator('[name="audio_files"]').setInputFiles([
    path.join(__dirname, '..', 'fixtures', 'chapter-01.mp3'),
    path.join(__dirname, '..', 'fixtures', 'chapter-02.mp3'),
  ]);

  try {
    await page.locator('#main-form button[type="submit"]').click();
    await expect(page.getByRole('heading', { name: title })).toBeVisible();
    await expect(page.getByText('chapter-01.mp3', { exact: false })).toBeVisible();
    await expect(page.getByText('chapter-02.mp3', { exact: false })).toBeVisible();
    await expect.poll(
      () => uploadEvents.filter(event => event === 'response').length
    ).toBe(2);
    expect(uploadEvents).toEqual(['request', 'response', 'request', 'response']);
  } catch (error) {
    testFailed = true;
    throw error;
  } finally {
    try {
      await removeBookIfPresent(page, title);
    } catch (cleanupError) {
      if (!testFailed) throw cleanupError;
      console.error('Browser-test cleanup also failed:', cleanupError);
    }
  }
});
