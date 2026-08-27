// E2E: catalog → audit service → 查询待审批记录 + order 查询订单详情 → 审计字段描述渲染
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
// 新建场景 (拿到空白画布)
await page.goto(`${BASE}/scenarios`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(800)
const newBtn = page.locator('button', { hasText: '新建' }).first()
await newBtn.click()
await page.waitForTimeout(1200)
console.log('after new scenario, url =', page.url())

// 进入步骤编辑 (step=4 即步骤编辑页)
const scId = page.url().match(/sc-[^/?]+/)?.[0]
await page.goto(`${BASE}/composer/${scId}?step=4`, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => document.querySelectorAll('.step-row, .empty-cta').length > 0, null, { timeout: 15000 })
await page.waitForTimeout(600)
console.log('canvas ready, steps =', await page.locator('.step-row').count())

// --- 加入 audit_audit_page ---
async function addEndpoint(system, service, endpointName) {
  await page.click('.add-step').catch(() => page.click('.empty-cta'))
  await page.waitForSelector('.tree-system-node', { timeout: 10000 })
  // toggle 语义: 仅当 caret 未展开时点击 (重复点击会收起)
  const sysNode = page.locator('.tree-system-node', { hasText: system }).first()
  if (await sysNode.locator('.caret').evaluate(el => !el.classList.contains('open'))) {
    await sysNode.click()
  }
  await page.waitForTimeout(300)
  const svcNode = page.locator('.tree-service-node', { hasText: service }).first()
  await svcNode.waitFor({ state: 'visible', timeout: 5000 })
  if (await svcNode.locator('.caret').evaluate(el => !el.classList.contains('open'))) {
    await svcNode.click()
  }
  await page.waitForTimeout(300)
  const ep = page.locator('.tree-endpoint-node', { hasText: endpointName }).first()
  await ep.waitFor({ state: 'visible', timeout: 5000 })
  await ep.scrollIntoViewIfNeeded()
  await ep.click()
  await page.waitForTimeout(400)
  const btn = page.locator('button', { hasText: '加入编排画布' }).first()
  await btn.click()
  await page.waitForTimeout(1500)
}

await addEndpoint('fin', 'audit', '查询待审批记录')
console.log('added audit_page, steps =', await page.locator('.step-row').count())

// --- 加入 order_order_detail ---
await addEndpoint('fin', 'order', '查询订单详情')
console.log('added order_detail, steps =', await page.locator('.step-row').count())

// 选中 step 1 (audit_page) 审计
await page.locator('.step-row').nth(0).click()
await page.waitForTimeout(800)

const audit1 = await page.evaluate(() => {
  const fields = [...document.querySelectorAll('.field')]
  return {
    fieldCount: fields.length,
    rows: fields.map(f => ({
      name: f.querySelector('.label-text')?.textContent?.trim(),
      desc: f.querySelector('.field-desc')?.textContent?.trim() ?? null,
      hasSelect: !!f.querySelector('select'),
    })),
    stepDesc: document.querySelector('.desc-readonly')?.textContent?.trim() ?? null,
  }
})
console.log('STEP1 (audit_page):', JSON.stringify(audit1, null, 1))

// 选中 step 2 (order_detail) 审计
await page.locator('.step-row').nth(1).click()
await page.waitForTimeout(800)
const audit2 = await page.evaluate(() => {
  const fields = [...document.querySelectorAll('.field')]
  return {
    fieldCount: fields.length,
    rows: fields.map(f => ({
      name: f.querySelector('.label-text')?.textContent?.trim(),
      desc: f.querySelector('.field-desc')?.textContent?.trim() ?? null,
    })),
    stepDesc: document.querySelector('.desc-readonly')?.textContent?.trim() ?? null,
  }
})
console.log('STEP2 (order_detail):', JSON.stringify(audit2, null, 1))

await page.screenshot({ path: `${OUT}/canvas-desc-1440.png`, fullPage: true })
console.log('saved canvas-desc-1440.png')
await ctx.close()
await browser.close()
