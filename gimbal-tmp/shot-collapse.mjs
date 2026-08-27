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
await page.goto(`${BASE}/composer/new`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1000)
await page.locator('.el-input__inner').first().fill('e2e-collapse')
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
await page.waitForSelector('.strategy-form', { timeout: 10000 })
await page.waitForTimeout(800)
// 全折叠态截图(初始预填)
await page.screenshot({ path: 'collapse-folded-1440.png', fullPage: true })
// 展开第一条 + 加 assign(自动展开)
await page.click('.strategy-form .sf-head')
await page.click('.add-strategy')
await page.waitForTimeout(400)
await page.click('.el-dropdown-menu__item:has-text("准备入参赋值")')
await page.waitForTimeout(800)
// 溢出审计: 每个 .ctl 是否超出其 .strategy-form 边界
const overflow = await page.evaluate(() => {
  const out = []
  for (const f of document.querySelectorAll('.strategy-form')) {
    const fr = f.getBoundingClientRect()
    for (const c of f.querySelectorAll('.ctl')) {
      const r = c.getBoundingClientRect()
      if (r.right > fr.right + 0.5 || r.left < fr.left - 0.5) {
        out.push({ ctl: r.right - fr.right, cls: c.className.slice(0, 30) })
      }
    }
  }
  return { overflowCount: out.length, detail: out.slice(0, 3) }
})
console.log('overflow audit:', JSON.stringify(overflow))
await page.screenshot({ path: 'collapse-expanded-1440.png', fullPage: true })
await ctx.close(); await browser.close()
