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
page.on('response', async (r) => {
  if (r.request().method() === 'POST' && r.url().includes('/scenarios')) {
    console.log('[net POST]', r.status(), r.url().slice(-40))
    try { console.log('  body:', (await r.text()).slice(0, 300)) } catch {}
  }
})
page.on('console', (m) => { if (m.type() === 'error') console.log('[console]', m.text().slice(0, 150)) })
await page.goto(`${BASE}/composer/new`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1000)
await page.locator('.el-input__inner').first().fill('e2e-strategy-X')
const stepTab = page.locator('[class*="step"]').filter({ hasText: '步骤编辑' }).last()
await stepTab.click()
await page.waitForFunction(() => !!document.querySelector('.add-step, .empty-cta'), null, { timeout: 15000 })
await page.click('.empty-cta')
await page.waitForSelector('.tree-system-node', { timeout: 10000 })
await page.waitForTimeout(500)
await page.click('.tree-system-node >> nth=0')
await page.waitForTimeout(600)
await page.click('.tree-endpoint-node:has-text("查询订单详情") >> nth=0')
await page.waitForTimeout(600)
await page.click('button:has-text("加入编排画布")')
await page.waitForSelector('.strategy-form', { timeout: 10000 })
await page.waitForTimeout(800)
await page.click('.add-strategy')
await page.waitForTimeout(600)
await page.locator('.el-dropdown-menu__item:visible', { hasText: '准备入参赋值' }).first().click()
await page.waitForTimeout(800)
console.log('before save kinds:', await page.evaluate(() => [...document.querySelectorAll('.sf-kind')].map(k => k.textContent?.trim())))
await page.locator('button:has-text("保存")').first().click()
await page.waitForTimeout(3500)
console.log('url after save:', page.url())
const st = await page.evaluate(() => ({
  msgs: [...document.querySelectorAll('.el-message')].map(m => m.textContent?.trim()),
  strategyForms: document.querySelectorAll('.strategy-form').length,
}))
console.log('state:', JSON.stringify(st))
await ctx.close(); await browser.close()
