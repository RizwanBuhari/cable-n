import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5173', viewport: { width: 1366, height: 900 } },
  webServer: [
    { command: '"../backend/.venv/Scripts/python.exe" -m uvicorn app.main:app --port 8000 --app-dir ../backend', url: 'http://127.0.0.1:8000/api/v1/health', reuseExistingServer: true, timeout: 60_000 },
    { command: 'npx vite --host 127.0.0.1', url: 'http://127.0.0.1:5173', reuseExistingServer: true, timeout: 60_000 },
  ],
})
