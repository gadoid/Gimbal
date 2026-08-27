// 截图脚本: 登录 → 注入 token → 抓配置页全页截图 (3 个视口宽度)
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:5173'
const API = 'http://127.0.0.1:8000'
const OUT = 'D:/Gimbal/Gimbal/gimbal-tmp'

const browser = await chromium.launch({ executablePath: 'C:/Users/jiaoshouxiang/AppData/Local/ms-playwright/chromium-1194/chrome-win/chrome.exe' })

// 1. 用 API 直接登录拿 token
const loginRes = await fetch(`${API}/api/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'uitest', password: 'UiTest123!' }),
})
if (!loginRes.ok) {
  console.error('login failed:', loginRes.status, await loginRes.text())
  process.exit(1)
}
const loginData = await loginRes.json()
const tokens = {
  accessToken: loginData.access_token,
  refreshToken: loginData.refresh_token,
}

for (const [name, width] of [['1920', 1920], ['1440', 1440], ['1024', 1024]]) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 } })
  // 2. 先开一个空页写 localStorage (5173 origin)
  const setup = await ctx.newPage()
  await setup.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
  await setup.evaluate((t) => {
    localStorage.setItem('gimbal-auth', JSON.stringify({ accessToken: t.accessToken, refreshToken: t.refreshToken }))
  }, tokens)
  await setup.close()
  // 3. 再开真实页面 — 同一 context 共享 localStorage
  const page = await ctx.newPage()
  await page.goto(`${BASE}/composer/sc-order-add?step=3`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1500)
  await page.screenshot({ path: `${OUT}/cfg2-${name}.png`, fullPage: true })
  console.log(`saved cfg2-${name}.png (url=${page.url()})`)
  await ctx.close()
}
await browser.close()
