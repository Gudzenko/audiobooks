const { expect, test } = require('@playwright/test');

async function login(page) {
  await page.goto('/auth/login/');
  await page.locator('[name="username"]').fill(
    process.env.TEST_ADMIN_USERNAME || 'admin',
  );
  await page.locator('[name="password"]').fill(
    process.env.TEST_ADMIN_PASSWORD || 'admin',
  );
  await page.getByRole('button', { name: /login|войти|zaloguj/i }).click();
  await expect(page).not.toHaveURL(/\/auth\/login\//);
}

async function openChat(page) {
  await login(page);
  await page.goto('/store/chat/');
  await expect(page.locator('#chat-form')).toBeVisible();
}

async function sendMessage(page, message) {
  await page.locator('#chat-input').fill(message);
  await page.locator('#chat-submit').click();
}

test('authenticated user can ask about the local catalog', async ({ page }) => {
  await openChat(page);
  await sendMessage(page, 'Show my books');

  await expect(page.locator('.chat-message-user')).toContainText('Show my books');
  const response = page.locator('.chat-message-assistant').last();
  await expect(response).toContainText('Foundation');
  await expect(response.getByRole('link', { name: /open book/i }).first()).toHaveAttribute(
    'href',
    /\/store\/books\//,
  );
  await expect(page.locator('.chat-message-status')).toHaveCount(0);
});

test('structured results are included in follow-up history', async ({ page }) => {
  await openChat(page);
  const requests = [];
  page.on('request', request => {
    if (
      request.method() === 'POST'
      && request.url().endsWith('/store/chat/message/')
    ) {
      requests.push(request.postDataJSON());
    }
  });

  await sendMessage(page, 'Show my books');
  await expect(page.locator('.chat-message-assistant')).toHaveCount(1);
  await sendMessage(page, 'Continue');
  await expect(page.locator('.chat-message-assistant')).toHaveCount(2);

  expect(requests).toHaveLength(2);
  expect(requests[1].history[1].role).toBe('assistant');
  expect(requests[1].history[1].content).toContain('Foundation');
});

test('clarification and unavailable web search are shown in the chat', async ({ page }) => {
  await openChat(page);

  await sendMessage(page, 'Уточни мой запрос');
  await expect(page.locator('.chat-message-assistant').last()).toContainText(
    'What should I show',
  );

  await sendMessage(page, 'Web unavailable');
  const response = page.locator('.chat-message-assistant').last();
  await expect(response).toContainText('web search is unavailable');
  await expect(response.locator('.chat-warning')).toHaveCount(1);
});

test('rich response renders formatting, sections, and safe external links', async ({ page }) => {
  await openChat(page);
  await page.route('**/store/chat/message/', async route => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        kind: 'answer',
        message: '## Result\n\n**Solaris**',
        message_html: '<h2>Result</h2><p><strong>Solaris</strong></p>',
        sections: [{
          title: 'Sources',
          items: [{
            title: 'Solaris',
            subtitle: 'Stanislaw Lem',
            status: 'Found',
            links: [{
              label: 'Open source',
              url: 'https://example.com/solaris',
              is_demo: false,
            }],
          }],
        }],
        warnings: [],
      }),
    });
  });

  await sendMessage(page, 'Find Solaris');

  const response = page.locator('.chat-message-assistant').last();
  await expect(response.locator('h2', { hasText: 'Result' })).toBeVisible();
  await expect(
    response.locator('.chat-bubble-rich > p strong', { hasText: 'Solaris' }),
  ).toBeVisible();
  const source = response.getByRole('link', { name: 'Open source' });
  await expect(source).toHaveAttribute('href', 'https://example.com/solaris');
  await expect(source).toHaveAttribute('target', '_blank');
  await expect(source).toHaveAttribute('rel', 'noopener noreferrer');
});

test('history is kept on the page and discarded after reload', async ({ page }) => {
  await openChat(page);
  const requests = [];
  await page.route('**/store/chat/message/', async route => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        kind: 'answer',
        message: 'Test answer',
        message_html: '<p>Test answer</p>',
        sections: [],
        warnings: [],
      }),
    });
  });

  await sendMessage(page, 'First question');
  await expect(page.locator('.chat-message-assistant')).toHaveCount(1);
  await sendMessage(page, 'Second question');
  await expect(page.locator('.chat-message-assistant')).toHaveCount(2);

  expect(requests[0].history).toEqual([]);
  expect(requests[1].history).toEqual([
    { role: 'user', content: 'First question' },
    { role: 'assistant', content: 'Test answer' },
  ]);

  await page.reload();
  await expect(page.locator('.chat-message')).toHaveCount(0);
  await sendMessage(page, 'Question after reload');
  await expect.poll(() => requests.length).toBe(3);
  expect(requests[2].history).toEqual([]);
});

test('large history is trimmed before the next request', async ({ page }) => {
  await openChat(page);
  const requests = [];
  await page.route('**/store/chat/message/', async route => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        kind: 'answer',
        message: 'Large answer',
        message_html: '<p>Large answer</p>',
        history_content: 'x'.repeat(6000),
        sections: [],
        warnings: [],
      }),
    });
  });

  for (let index = 1; index <= 5; index += 1) {
    await sendMessage(page, `Question ${index}`);
    await expect(page.locator('.chat-message-assistant')).toHaveCount(index);
  }

  const sentHistory = requests[4].history;
  const totalCharacters = sentHistory.reduce(
    (total, item) => total + item.content.length,
    0,
  );
  expect(totalCharacters).toBeLessThanOrEqual(18000);
  expect(sentHistory.at(-1).content).toHaveLength(6000);
  expect(sentHistory.some(item => item.content === 'Question 1')).toBeFalsy();
});

test('clear button removes visible messages and conversation history', async ({ page }) => {
  await openChat(page);
  const requests = [];
  await page.route('**/store/chat/message/', async route => {
    requests.push(route.request().postDataJSON());
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        kind: 'answer',
        message: 'Test answer',
        message_html: '<p>Test answer</p>',
        sections: [],
        warnings: [],
      }),
    });
  });

  await sendMessage(page, 'Before clear');
  await expect(page.locator('.chat-message-assistant')).toHaveCount(1);
  await page.locator('#clear-chat').click();
  await expect(page.locator('.chat-message-user')).toHaveCount(0);
  await expect(page.locator('.chat-message-assistant')).toHaveCount(1);

  await sendMessage(page, 'After clear');
  await expect.poll(() => requests.length).toBe(2);
  expect(requests[1].history).toEqual([]);
});

test('server errors are displayed without breaking the input', async ({ page }) => {
  await openChat(page);
  await page.route('**/store/chat/message/', async route => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'The chat service is temporarily unavailable.' }),
    });
  });

  await sendMessage(page, 'Trigger an error');

  await expect(page.locator('.chat-message-assistant').last()).toContainText(
    'temporarily unavailable',
  );
  await expect(page.locator('#chat-input')).toBeEnabled();
  await expect(page.locator('#chat-submit')).toBeEnabled();
  await expect(page.locator('.chat-message-status')).toHaveCount(0);
});

test('failed request is not included in the next request history', async ({ page }) => {
  await openChat(page);
  const requests = [];
  let requestNumber = 0;
  await page.route('**/store/chat/message/', async route => {
    requests.push(route.request().postDataJSON());
    requestNumber += 1;
    if (requestNumber === 1) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ error: 'Temporary failure.' }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        kind: 'answer',
        message: 'Recovered',
        message_html: '<p>Recovered</p>',
        sections: [],
        warnings: [],
      }),
    });
  });

  await sendMessage(page, 'Failed question');
  await expect(page.locator('.chat-message-assistant').last()).toContainText(
    'Temporary failure',
  );
  await sendMessage(page, 'New question');
  await expect(page.locator('.chat-message-assistant').last()).toContainText(
    'Recovered',
  );

  expect(requests).toHaveLength(2);
  expect(requests[1].history).toEqual([]);
  await expect(page.locator('.chat-message-user')).toHaveCount(2);
});
