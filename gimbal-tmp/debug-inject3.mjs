import { chromium } from 'playwright'
const BASE = 'http://127.0.0.1:5173'
const API = 'http://127.0.0.1:8000'
const browser = await chromium.launch({ executablePath: 'C:/Users/jiaoshouxiang/AppData/Local/ms-playwright/chromium-1194/chrome-win/chrome.exe' })
const loginRes = await fetch(`${API}/api/auth/login`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: 'uitest', password: 'UiTest123!' }) })
const loginData = await loginRes.json()
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const setup = await ctx.newPage()
await setup.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
await setup.evaluate((t) => { localStorage.setItem('gimbal-auth', JSON.stringify({ accessToken: t.access_token, refreshToken: t.refresh_token })) }, loginData)
await setup.close()
const page = await ctx.newPage()
page.on('console', (m) => {
  const args = m.args()
  if (m.type() === 'error' || m.text().includes('Unhandled')) {
    // 展开第一个 arg 的完整属性
    try {
      const a0 = args[0]?.evaluate?.deep ? null : null
    } catch {}
    console.log('CONSOLE:', m.text().slice(0, 100))
    for (const a of args.slice(1, 3)) {
      try {
        const json = a.evaluate((o) => {
          if (o instanceof Error) return o.stack || String(o)
          return JSON.stringify(o)?.slice(0, 300)
        })
        console.log('  ARG:', json)
      } catch (e) { console.log('  ARG?(unserializable)') }
    }
  }
})
await page.goto(`${BASE}/composer/new`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1000)
await page.locator('.el-input__inner').first().fill('dbg3')
await page.locator('.el-form-item__label:has-text("module")').locator('..').locator('input').first().fill('e2e')
await page.locator('[class*="step"]').filter({ hasText: '步骤编辑' }).last().click()
await page.waitForFunction(() => !!document.querySelector('.add-step, .empty-cta'), null, { timeout: 15000 })
await page.click('.empty-cta')
await page.waitForSelector('.tree-system-node', { timeout: 10000 })
await page.waitForTimeout(500)
await page.click('.tree-system-node >> nth=0')
await page.waitForTimeout(600)
await page.locator('.tree-endpoint-node:has-text("查询订单详情")').first().click()
await page.waitForTimeout(600)
await page.click('button:has-text("加入编排画布")')
await page.waitForTimeout(1200)
await page.click('button:has-text("+ 新增 header")')
await page.waitForTimeout(300)
await page.click('.hdr-pick')
await page.waitForTimeout(600)
await page.locator('.el-dialog .el-select').click()
await page.waitForTimeout(500)
await page.locator('.el-select-dropdown__item:has-text("qa-e2e")').first().click()
await page.waitForTimeout(300)
await page.locator('.el-dialog__footer button:has-text("确认插入")').click()
await page.waitForTimeout(800)
console.log('val:', await page.evaluate(() => document.querySelector('.hdr-val input')?.value))
await browser.close()
