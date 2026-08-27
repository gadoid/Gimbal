// 播种 (若空) → 验证 description 只读
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
  const svcNode = page.locator('.tree-service-node').first()
  if (await svcNode.count()) { await svcNode.click(); await page.waitForTimeout(400) }
  const epNode = page.locator('.tree-endpoint-node').first()
  if (await epNode.count()) {
    await epNode.click()
    await page.waitForTimeout(800)
    const joinBtn = page.locator('button:has-text("加入编排画布")')
    await joinBtn.waitFor({ timeout: 8000 })
    await joinBtn.click()
    await page.waitForTimeout(1500)
  }
} else {
  await page.click('.step-row >> nth=0')
  await page.waitForTimeout(500)
}

const audit = await page.evaluate(() => {
  const items = [...document.querySelectorAll('.el-form-item')]
  const descItem = items.find(l => l.querySelector('.el-form-item__label')?.textContent?.includes('description'))
  const input = descItem?.querySelector('input, textarea')
  const ro = descItem?.querySelector('.desc-readonly')
  return {
    descItemFound: !!descItem,
    hasEditableInput: !!input,
    readonlyEl: ro ? { text: ro.textContent?.trim().slice(0, 50), tag: ro.tagName } : null,
  }
})
console.log(JSON.stringify(audit, null, 1))
await page.screenshot({ path: 'D:/Gimbal/Gimbal/gimbal-tmp/canvas-v3-1440.png', fullPage: true })
console.log('saved canvas-v3-1440.png')
await ctx.close()
await browser.close()
