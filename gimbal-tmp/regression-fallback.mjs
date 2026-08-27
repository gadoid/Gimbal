// 降级回归: strategy-catalog 不可用 → 旧 extract 专用 UI 兜底
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
// 拦截 strategy-catalog → 502 (plate 挂了的形状)
await ctx.route('**/api/strategy-catalog**', (route) => route.fulfill({ status: 502, contentType: 'application/json', body: '{"detail":"plate_unavailable"}' }))
await page.goto(`${BASE}/composer/new`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1000)
await page.locator('.el-input__inner').first().fill('e2e-fallback')
await page.locator('.el-form-item__label:has-text("module")').locator('..').locator('input').first().fill('e2e')
await page.locator('[class*="step"]').filter({ hasText: '步骤编辑' }).last().click()
await page.waitForFunction(() => !!document.querySelector('.add-step, .empty-cta'), null, { timeout: 15000 })
await page.click('.empty-cta')
await page.waitForSelector('.tree-system-node', { timeout: 10000 })
await page.waitForTimeout(500)
await page.click('.tree-system-node >> nth=0')
await page.waitForTimeout(600)
await page.click('.tree-endpoint-node:has-text("查询订单详情") >> nth=0')
await page.waitForTimeout(600)
await page.click('button:has-text("加入编排画布")')
await page.waitForTimeout(1200)
const state = await page.evaluate(() => ({
  fallbackUiVisible: !!document.querySelector('.add-extract'),
  strategyAreaGone: !document.querySelector('.strategy-area'),
  extractRows: document.querySelectorAll('.extract-row').length,
}))
console.log('fallback:', JSON.stringify(state))
if (!state.fallbackUiVisible || !state.strategyAreaGone) { console.error('FAIL: fallback UI not shown'); process.exit(1) }
console.log('PASS: catalog 502 → 降级 extract 专用 UI')
// 加一条 extract 验证可用
await page.click('.add-extract')
await page.waitForTimeout(500)
const after = await page.evaluate(() => ({ extractRows: document.querySelectorAll('.extract-row').length }))
console.log('after add:', JSON.stringify(after))
if (after.extractRows !== 1) { console.error('FAIL: cannot add extract in fallback'); process.exit(1) }
console.log('PASS: 降级模式下 extract 可添加')
await page.screenshot({ path: 'regression-fallback-1440.png', fullPage: true })
await ctx.close(); await browser.close()
