// 端到端: 目录加 settlement.create_order → 验证 FieldForm 字段 description 渲染
import { chromium } from 'playwright'
const BASE = 'http://127.0.0.1:5173'
const API = 'http://127.0.0.1:8000'
const browser = await chromium.launch({ executablePath: 'C:/Users/jiaoshouxiang/AppData/Local/ms-playwright/chromium-1194/chrome-win/chrome.exe' })
const loginRes = await fetch(`${API}/api/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
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
await page.goto(`${BASE}/composer/sc-order-add?step=4`, { waitUntil: 'domcontentloaded' })
await page.waitForFunction(() => !!document.querySelector('.add-step, .empty-cta'), null, { timeout: 15000 })

if (await page.locator('.empty-cta').count()) {
  await page.click('.empty-cta')
  await page.waitForSelector('.tree-system-node', { timeout: 10000 })
  await page.waitForTimeout(600)
  await page.click('.tree-system-node >> nth=0')
  await page.waitForTimeout(400)
  // 展开所有服务, 找 settlement 服务节点
  const svcNodes = page.locator('.tree-service-node')
  const n = await svcNodes.count()
  let joined = false
  for (let i = 0; i < n; i++) {
    const txt = await svcNodes.nth(i).textContent()
    if (txt && txt.includes('settlement')) {
      await svcNodes.nth(i).click()
      await page.waitForTimeout(400)
      const ep = page.locator('.tree-endpoint-node', { hasText: '创建结算单' }).first()
      if (await ep.count()) {
        await ep.click()
        await page.waitForTimeout(900)
        const joinBtn = page.locator('button:has-text("加入编排画布")')
        await joinBtn.waitFor({ timeout: 8000 })
        await joinBtn.click()
        await page.waitForTimeout(1500)
        joined = true
      }
      break
    }
  }
  if (!joined) { console.log('FALLBACK: settlement not found, joining first endpoint'); }
}

await page.waitForTimeout(800)
const audit = await page.evaluate(() => {
  const fields = [...document.querySelectorAll('.field-form .field')]
  const descs = [...document.querySelectorAll('.field-desc')].map(d => d.textContent?.trim())
  return {
    fieldCount: fields.length,
    fieldNames: fields.map(f => f.querySelector('.label-text')?.textContent?.trim()),
    descCount: descs.length,
    descs: descs.slice(0, 8),
    descReadonly: document.querySelector('.desc-readonly')?.textContent?.trim() || null,
  }
})
console.log(JSON.stringify(audit, null, 1))
await page.screenshot({ path: 'D:/Gimbal/Gimbal/gimbal-tmp/canvas-v4-1440.png', fullPage: true })
console.log('saved canvas-v4-1440.png')
await ctx.close()
await browser.close()
