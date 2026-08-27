// 证据采集: 量化配置页各卡片内元素的实际几何位置 (对齐检测)
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

for (const width of [1440]) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 } })
  const setup = await ctx.newPage()
  await setup.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
  await setup.evaluate((t) => {
    localStorage.setItem('gimbal-auth', JSON.stringify({ accessToken: t.access_token, refreshToken: t.refresh_token }))
  }, loginData)
  await setup.close()
  const page = await ctx.newPage()
  await page.goto(`${BASE}/composer/sc-order-add?step=3`, { waitUntil: 'domcontentloaded' })
  // 等 URL 不再是 /login 且卡片出现 (路由 guard 走完 fetchMe)
  await page.waitForFunction(() => document.querySelectorAll('.c-card').length > 0, null, { timeout: 15000 })
  await page.waitForTimeout(1200)

  const report = await page.evaluate(() => {
    const out = []
    const rect = (el) => {
      const r = el.getBoundingClientRect()
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }
    }
    document.querySelectorAll('.c-card').forEach((card, ci) => {
      const title = card.querySelector('h3')?.textContent?.trim() || `card#${ci}`
      const entry = { title, card: rect(card), items: [] }
      const walk = (root) => {
        root.querySelectorAll(':scope > *').forEach((child) => {
          if (child.classList.contains('c-card-head')) return
          const cs = getComputedStyle(child)
          if (cs.display === 'none') return
          const controls = child.matches('.el-input__wrapper, .el-select__wrapper, .el-switch, .el-input-number, textarea, button')
            ? [child] : [...child.querySelectorAll('.el-input__wrapper, .el-select__wrapper, .el-switch, .el-input-number, textarea, button')]
          controls.forEach((c) => {
            const ccs = getComputedStyle(c)
            if (ccs.display === 'none' || ccs.visibility === 'hidden') return
            const ph = c.closest('.el-input')?.querySelector('input')?.placeholder || ''
            entry.items.push({ what: c.classList[0] || c.tagName.toLowerCase(), ph: ph.slice(0, 24), ...rect(c) })
          })
        })
      }
      walk(card)
      out.push(entry)
    })
    return out
  })
  console.log(JSON.stringify(report, null, 1))
  await ctx.close()
}
await browser.close()
