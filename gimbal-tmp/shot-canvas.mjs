// 截图: 步骤编辑页 (step=4) — 验证 api 只读缩略行
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:5173'
const API = 'http://127.0.0.1:8000'
const OUT = 'D:/Gimbal/Gimbal/gimbal-tmp'

const browser = await chromium.launch({ executablePath: 'C:/Users/jiaoshouxiang/AppData/Local/ms-playwright/chromium-1194/chrome-win/chrome.exe' })
const loginRes = await fetch(`${API}/api/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'uitest', password: 'UiTest123!' }),
})
if (!loginRes.ok) { console.error('login failed:', loginRes.status); process.exit(1) }
const loginData = await loginRes.json()

const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const setup = await ctx.newPage()
await setup.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
await setup.evaluate((t) => {
  localStorage.setItem('gimbal-auth', JSON.stringify({ accessToken: t.access_token, refreshToken: t.refresh_token }))
}, loginData)
await setup.close()

const page = await ctx.newPage()
await page.goto(`${BASE}/composer/sc-order-add?step=4`, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => document.querySelectorAll('.col, .three-col > *').length > 0, null, { timeout: 15000 })
await page.waitForTimeout(1200)

// DOM 验证: api-summary 存在且含徽标; 表单里不再有 method/service/path 输入项
const audit = await page.evaluate(() => {
  const formItems = [...document.querySelectorAll('.el-form-item__label')].map(l => l.textContent?.trim())
  const summary = document.querySelector('.api-summary')
  const badges = summary ? [...summary.querySelectorAll('.method-badge, .svc-tag, .ep-path')].map(b => b.textContent?.trim()) : null
  return {
    url: location.pathname,
    formLabels: formItems,
    apiSummaryExists: !!summary,
    apiSummaryBadges: badges,
    titleInputExists: !!document.querySelector('.title-input'),
  }
})
console.log(JSON.stringify(audit, null, 1))
await page.screenshot({ path: `${OUT}/canvas-v2-1440.png`, fullPage: true })
console.log('saved canvas-v2-1440.png')
await ctx.close()
await browser.close()
