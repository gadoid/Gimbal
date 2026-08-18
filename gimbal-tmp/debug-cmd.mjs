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
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log('[console]', m.type(), m.text().slice(0, 200)) })
page.on('response', (r) => { if (r.url().includes('strategy-catalog')) console.log('[net]', r.status(), r.url().slice(-60)) })
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
await page.waitForTimeout(1500) // 等 prefetch 完成
const before = await page.evaluate(() => ({
  addStrategy: !!document.querySelector('.add-strategy'),
  msg: [...document.querySelectorAll('.el-message')].map(m => m.textContent?.trim()),
}))
console.log('before:', JSON.stringify(before))
await page.click('.add-strategy')
await page.waitForTimeout(600)
const menuState = await page.evaluate(() => ({
  visibleMenus: [...document.querySelectorAll('.el-dropdown-menu')].filter(m => m.offsetParent !== null).length,
  items: [...document.querySelectorAll('.el-dropdown-menu__item')].filter(i => i.offsetParent !== null).map(i => i.textContent?.trim()),
}))
console.log('menu open:', JSON.stringify(menuState))
const item = page.locator('.el-dropdown-menu__item:visible', { hasText: '准备入参赋值' }).first()
console.log('item count:', await item.count())
await item.click()
await page.waitForTimeout(1000)
const after = await page.evaluate(() => ({
  strategyForms: document.querySelectorAll('.strategy-form').length,
  kinds: [...document.querySelectorAll('.sf-kind')].map(k => k.textContent?.trim()),
  msg: [...document.querySelectorAll('.el-message')].map(m => m.textContent?.trim()),
}))
console.log('after:', JSON.stringify(after))
await ctx.close(); await browser.close()
