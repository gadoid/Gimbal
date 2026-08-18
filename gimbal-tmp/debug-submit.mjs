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
let navCount = 0
page.on('framenavigated', (f) => { if (f === page.mainFrame) navCount++ })
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
await page.waitForTimeout(500)
// 检查按钮的 form 归属与 type
const btnInfo = await page.evaluate(() => {
  const b = document.querySelector('.add-strategy')
  if (!b) return null
  const form = b.closest('form')
  return { btnType: b.getAttribute('type'), inForm: !!form, formClass: form?.className || null }
})
console.log('before click btnInfo:', JSON.stringify(btnInfo), 'navCount:', navCount)
await page.click('.add-strategy')
await page.waitForTimeout(800)
const after = await page.evaluate(() => ({
  addStrategyExists: !!document.querySelector('.add-strategy'),
  strategyForms: document.querySelectorAll('.strategy-form').length,
  dropdownItems: [...document.querySelectorAll('.el-dropdown-menu__item')].map(i => i.textContent?.trim()),
}))
console.log('after click:', JSON.stringify(after), 'navCount:', navCount, 'url:', page.url())
await ctx.close(); await browser.close()
