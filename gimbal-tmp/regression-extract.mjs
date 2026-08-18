// 存量回归: 已有 extract 策略的场景,加载后 extract 仍正常显示/编辑
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
// 找一个带 extract 的存量场景: 列出 scenarios,逐个 GET draft 看 strategy
const token = loginData.access_token
const list = await (await fetch(`${API}/api/scenarios`, { headers: { Authorization: 'Bearer ' + token } })).json()
const scenarios = Array.isArray(list) ? list : (list.items || [])
let target = null
for (const s of scenarios) {
  const sid = s.meta?.scenarioId
  if (!sid) continue
  const d = await (await fetch(`${API}/api/scenarios/${sid}/draft`, { headers: { Authorization: 'Bearer ' + token } })).json().catch(() => null)
  const steps = d?.definition?.steps || []
  const hasExtract = steps.some((st) => (st.strategy || []).some((x) => x.kind === 'extract'))
  if (hasExtract) { target = { sid, name: s.meta.name }; break }
}
if (!target) { console.log('SKIP: no existing scenario with extract strategies found'); process.exit(0) }
console.log('target scenario:', JSON.stringify(target))
await page.goto(`${BASE}/composer/${target.sid}?step=4`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2500)
const state = await page.evaluate(() => {
  const forms = [...document.querySelectorAll('.strategy-form')]
  return {
    strategyForms: forms.length,
    kinds: [...document.querySelectorAll('.sf-kind')].map(k => k.textContent?.trim()),
    // 通用策略区下 extract 也会渲染成 strategy-form(kind=extract, phase=after_request 绿边)
    extractInputs: [...document.querySelectorAll('.strategy-form')].map(f =>
      [...f.querySelectorAll('input.ctl, select.ctl')].map(i => i.value).slice(0, 6)),
    fallbackExtractRows: document.querySelectorAll('.extract-row').length,
  }
})
console.log('loaded:', JSON.stringify(state, null, 1))
await page.screenshot({ path: 'regression-extract-1440.png', fullPage: true })
await ctx.close(); await browser.close()
