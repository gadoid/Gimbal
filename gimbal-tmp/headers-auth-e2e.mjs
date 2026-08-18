// E2E: #1 headers KV 化 + 认证引用(headers-auth)
// 链路: 加 header → ⓘ 选认证 → value 变模板串 → 徽章状态 → 悬空红徽章 → 保存 reload 仍在
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

// 前置: 保证 owner 下存在 alias=qa-e2e 的认证(存在则跳过创建)
{
  const listRes = await fetch(`${API}/api/auths`, {
    headers: { Authorization: `Bearer ${loginData.access_token}` },
  })
  const auths = await listRes.json()
  if (!auths.some((a) => a.alias === 'qa-e2e')) {
    const cr = await fetch(`${API}/api/auths`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${loginData.access_token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        alias: 'qa-e2e', url: 'http://auth.example/login',
        username: 'qa-user', password: 'qa-pass', token_type: 'bearer',
      }),
    })
    if (!cr.ok) { console.error('create auth failed:', cr.status, await cr.text()); process.exit(1) }
  }
}

const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const setup = await ctx.newPage()
await setup.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
await setup.evaluate((t) => {
  localStorage.setItem('gimbal-auth', JSON.stringify({ accessToken: t.access_token, refreshToken: t.refresh_token }))
}, loginData)
await setup.close()
const page = await ctx.newPage()

// ── 新建场景进画布(同 strategy-e2e 的 SPA 导航模式) ──
await page.goto(`${BASE}/composer/new`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1000)
await page.locator('.el-input__inner').first().fill('e2e-headers-auth')
await page.locator('.el-form-item__label:has-text("module")').locator('..').locator('input').first().fill('e2e')
await page.locator('[class*="step"]').filter({ hasText: '步骤编辑' }).last().click()
await page.waitForFunction(() => !!document.querySelector('.add-step, .empty-cta'), null, { timeout: 15000 })

// 加 endpoint
if (await page.locator('.empty-cta').count()) await page.click('.empty-cta')
else await page.click('.add-step')
await page.waitForSelector('.tree-system-node', { timeout: 10000 })
await page.waitForTimeout(500)
await page.click('.tree-system-node >> nth=0')
await page.waitForTimeout(600)
await page.locator('.tree-endpoint-node:has-text("查询订单详情")').first().click()
await page.waitForTimeout(600)
await page.click('button:has-text("加入编排画布")')
await page.waitForTimeout(1200)

// ── headers KV 行 ──
await page.click('button:has-text("+ 新增 header")')
await page.waitForTimeout(300)
let audit = await page.evaluate(() => {
  const rows = [...document.querySelectorAll('.hdr-row')]
  return {
    rows: rows.length,
    keys: [...document.querySelectorAll('.hdr-key input')].map((i) => i.value),
    picks: document.querySelectorAll('.hdr-pick').length,
  }
})
console.log('initial hdr:', JSON.stringify(audit))
if (audit.rows !== 1 || audit.picks !== 1) { console.error('FAIL: KV 行/ⓘ 缺失'); process.exit(1) }
console.log('PASS: KV 行 + ⓘ 渲染')

// 填 key,ⓘ 选认证
await page.locator('.hdr-key input').first().fill('Authorization')
await page.click('.hdr-pick')
await page.waitForSelector('.el-dialog:has-text("选择认证")', { timeout: 8000 })
await page.locator('.el-dialog .el-select').click()
await page.waitForTimeout(400)
await page.locator('.el-select-dropdown__item:has-text("qa-e2e")').first().click()
await page.click('.el-dialog button:has-text("确认插入")')
await page.waitForTimeout(400)

audit = await page.evaluate(() => ({
  val: document.querySelector('.hdr-val input')?.value,
  chips: [...document.querySelectorAll('.ref-chip')].map((c) => ({
    text: c.textContent?.trim(),
    dangling: c.classList.contains('dangling'),
  })),
}))
console.log('after pick:', JSON.stringify(audit))
if (audit.val !== '${auth.qa-e2e.token}') { console.error('FAIL: ⓘ 未注入模板串, got', audit.val); process.exit(1) }
if (!audit.chips.length || audit.chips[0].dangling) { console.error('FAIL: 绿徽章缺失/误判悬空'); process.exit(1) }
console.log('PASS: ⓘ 注入 ${auth.qa-e2e.token} + 绿徽章')

// 手打悬空引用 → 红徽章
await page.locator('.hdr-val input').first().fill('Bearer ${auth.nope.token}')
await page.waitForTimeout(300)
audit = await page.evaluate(() => [...document.querySelectorAll('.ref-chip')].map((c) => ({
  text: c.textContent?.trim(),
  dangling: c.classList.contains('dangling'),
})))
console.log('dangling:', JSON.stringify(audit))
if (!audit[0]?.dangling) { console.error('FAIL: 悬空引用未标红'); process.exit(1) }
console.log('PASS: 悬空引用红徽章 + 提示文案')

// 改回合法值,保存
await page.locator('.hdr-val input').first().fill('${auth.qa-e2e.token}')
await page.waitForTimeout(300)
const saveBtn = page.locator('button:has-text("保存")').first()
if (await saveBtn.count()) {
  await saveBtn.click()
  await page.waitForTimeout(2500)
}
const sidList = await page.evaluate(async (nm) => {
  const token = JSON.parse(localStorage.getItem('gimbal-auth') || '{}')
  const r = await fetch('/api/scenarios?q=' + encodeURIComponent(nm), {
    headers: { Authorization: 'Bearer ' + token.accessToken },
  })
  const j = await r.json()
  return (Array.isArray(j) ? j : []).map((s) => s.meta?.scenarioId)
}, 'e2e-headers-auth')
const sid = sidList[0]
if (!sid) { console.error('FAIL: scenario not saved'); process.exit(1) }

// reload 验持久(headers 形状不变 → KV 行回显)
await page.goto(`${BASE}/composer/${sid}?step=4`, { waitUntil: 'domcontentloaded' })
await page.waitForSelector('.hdr-row', { timeout: 15000 })
audit = await page.evaluate(() => ({
  keys: [...document.querySelectorAll('.hdr-key input')].map((i) => i.value),
  val: document.querySelector('.hdr-val input')?.value,
}))
console.log('after reload:', JSON.stringify(audit))
if (!audit.keys.includes('Authorization') || audit.val !== '${auth.qa-e2e.token}') {
  console.error('FAIL: headers 未持久/回显错'); process.exit(1)
}
console.log('PASS: reload 后 headers 仍在(KV 回显)')

await page.screenshot({ path: `${OUT}/headers-auth-1440.png`, fullPage: true })
await ctx.close()
await browser.close()
console.log('ALL E2E PASS')
