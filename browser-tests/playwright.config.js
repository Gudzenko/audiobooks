const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 120000,
  use: {
    baseURL: process.env.BASE_URL || 'http://web:8000',
    browserName: 'chromium',
    trace: 'retain-on-failure',
  },
});
