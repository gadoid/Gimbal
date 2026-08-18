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
page.on('framenavigated', (f) => { if (f === page.mainFrame) console.log('[nav]', f.url()) })
await page.goto(`${BASE}/composer/new?step=4`, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => !!document.querySelector('.add-step, .empty-cta'), null, { timeout: 15000 })
if (await page.locator('.empty-cta').count()) await page.click('.empty-cta')
else await page.click('.add-step')
await page.waitForSelector('.tree-system-node', { timeout: 10000 })
await page.waitForTimeout(500)
await page.click('.tree-system-node >> nth=0')
await page.waitForTimeout(600)
await page.click('.tree-endpoint-node:has-text("查询订单详情") >> nth=0')
await page.waitForTimeout(600)
await page.click('button:has-text("加入编排画布")')
await page.waitForSelector('.strategy-form', { timeout: 10000 })
await page.waitForTimeout(1000)
const saveBtn = page.locator('button:has-text("保存")').first()
console.log('saveBtn count:', await saveBtn.count(), 'text:', await saveBtn.textContent().catch(() => null))
await saveBtn.click()
await page.waitForTimeout(3000)
console.log('url after save+3s:', page.url())
// 尝试直接 goto step=4
const persistUrl = page.url().replace(/([?&])step=\d/, '$1step=4')
console.log('persistUrl:', persistUrl)
await page.goto(persistUrl.includes('/composer/') ? persistUrl : `${BASE}/composer/new?step=4`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2500)
const state = await page.evaluate(() => ({
  strategyForms: document.querySelectorAll('.strategy-form').length,
  kinds: [...document.querySelectorAll('.sf-kind')].map(k => k.textContent?.trim()),
  stepRows: document.querySelectorAll('.step-row').length,
  emptyCta: !!document.querySelector('.empty-cta'),
  msg: [...document.querySelectorAll('.el-message')].map(m => m.textContent?.trim()),
}))
console.log('after goto:', JSON.stringify(state))
await page.screenshot({ path: 'debug-persist.png' })
await ctx.close(); await browser.close()
