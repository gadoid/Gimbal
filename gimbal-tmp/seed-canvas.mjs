// 通过 UI: 目录树选接口 → 加入编排画布 → 验证 api-summary 只读缩略行
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
await page.waitForFunction(() => !!document.querySelector('.add-step, .empty-cta'), null, { timeout: 15000 })

// 空态 → 进目录
if (await page.locator('.empty-cta').count()) {
  await page.click('.empty-cta')
  // 等树出现
  await page.waitForSelector('.tree-system-node', { timeout: 10000 })
  await page.waitForTimeout(600)
  // 1. 展开第一个系统
  await page.click('.tree-system-node >> nth=0')
  await page.waitForTimeout(400)
  // 2. 展开第一个服务
  const svcNode = page.locator('.tree-service-node').first()
  if (await svcNode.count()) {
    await svcNode.click()
    await page.waitForTimeout(400)
  }
  // 3. 选第一个接口
  const epNode = page.locator('.tree-endpoint-node').first()
  if (await epNode.count()) {
    await epNode.click()
    await page.waitForTimeout(800)
    // 4. 加入编排画布
    const joinBtn = page.locator('button:has-text("加入编排画布")')
    await joinBtn.waitFor({ timeout: 8000 })
    await joinBtn.click()
    await page.waitForTimeout(1500)
  } else {
    console.log('no endpoint node in tree')
  }
}

await page.waitForTimeout(800)
const audit = await page.evaluate(() => {
  const formItems = [...document.querySelectorAll('.el-form-item__label')].map(l => l.textContent?.trim())
  const summary = document.querySelector('.api-summary')
  const badges = summary ? [...summary.querySelectorAll('.method-badge, .svc-tag, .ep-path')].map(b => b.textContent?.trim()) : null
  const sumRect = summary ? summary.getBoundingClientRect() : null
  return {
    url: location.pathname + location.search,
    steps: document.querySelectorAll('.step-row').length,
    formLabels: formItems,
    apiSummary: sumRect ? { x: Math.round(sumRect.x), y: Math.round(sumRect.y), w: Math.round(sumRect.width), h: Math.round(sumRect.height) } : null,
    badges,
    titleInputExists: !!document.querySelector('.title-input'),
  }
})
console.log(JSON.stringify(audit, null, 1))
await page.screenshot({ path: `${OUT}/canvas-v2-1440.png`, fullPage: true })
console.log('saved canvas-v2-1440.png')
await ctx.close()
await browser.close()
