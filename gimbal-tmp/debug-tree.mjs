import { chromium } from 'playwright'
const BASE = 'http://127.0.0.1:5173'
const API = 'http://127.0.0.1:8000'
const browser = await chromium.launch({ executablePath: 'C:/Users/jiaoshouxiang/AppData/Local/ms-playwright/chromium-1194/chrome-win/chrome.exe' })
const loginRes = await fetch(`${API}/api/auth/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'uitest', password: 'UiTest123!' }),
})
const loginData = await loginRes.json()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const setup = await ctx.newPage()
await setup.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
await setup.evaluate((t) => {
  localStorage.setItem('gimbal-auth', JSON.stringify({ accessToken: t.access_token, refreshToken: t.refresh_token }))
}, loginData)
await setup.close()
const page = await ctx.newPage()
await page.goto(`${BASE}/composer/new?step=4`, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => !!document.querySelector('.add-step, .empty-cta'), null, { timeout: 15000 })
if (await page.locator('.empty-cta').count()) await page.click('.empty-cta')
else await page.click('.add-step')
await page.waitForSelector('.tree-system-node', { timeout: 10000 })
await page.waitForTimeout(800)
await page.click('.tree-system-node >> nth=0')
await page.waitForTimeout(800)
const state = await page.evaluate(() => ({
  systems: [...document.querySelectorAll('.tree-system-node')].map(n => n.textContent?.trim()),
  services: [...document.querySelectorAll('.tree-service-node')].map(n => n.textContent?.trim()),
  endpoints: [...document.querySelectorAll('.tree-endpoint-node')].map(n => n.textContent?.trim()),
}))
console.log(JSON.stringify(state, null, 1))
await page.screenshot({ path: 'D:/Gimbal/Gimbal/gimbal-tmp/debug-tree.png' })
await ctx.close(); await browser.close()
