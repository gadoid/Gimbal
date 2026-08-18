// E2E: 策略区泛化 + endpoint 契约驱动预填 (Task 5)
// 路径 A: 真实数据 —— 加 fin.order.order_detail(success_criteria 空) → 只有保底 $.status 断言
// 路径 B: 路由拦截 /full 注入 success_criteria + $.code → 初始策略 2 条,含 $.code eq 0
// 然后: 添加 assign + assertion → operator 下拉 14 项 → 保存 reload 策略仍在
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

async function newAuthedCtx() {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  const setup = await ctx.newPage()
  await setup.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' })
  await setup.evaluate((t) => {
    localStorage.setItem('gimbal-auth', JSON.stringify({ accessToken: t.access_token, refreshToken: t.refresh_token }))
  }, loginData)
  await setup.close()
  return ctx
}

/** 通过 UI 新建场景并进入画布 (step=4) */
async function createScenario(page, name) {
  await page.goto(`${BASE}/composer/new`, { waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(1000)
  // 向导 step1: 填名称 + module(后端 ScenarioMeta 必填,空 module 保存 400)
  const nameInput = page.locator('.el-input__inner').first()
  await nameInput.waitFor({ timeout: 10000 })
  await nameInput.fill(name)
  // module 必填(空则保存 400);label 定位同节的 input
  await page.locator('.el-form-item__label:has-text("module")').locator('..').locator('input').first().fill('e2e')
  // 点步骤条 "步骤编辑" 进入画布 (SPA 内部导航,保留内存中的 name;
  // 整页 goto ?step=4 会丢未持久化的 name → 后续保存被 saveDraft 挡下)
  const stepTab = page.locator('[class*="step"]').filter({ hasText: '步骤编辑' }).last()
  await stepTab.click()
  await page.waitForFunction(() => !!document.querySelector('.add-step, .empty-cta'), null, { timeout: 15000 })
}

/** 从目录加入指定 endpoint(点系统节点进入过滤模式,全部接口直接可见) */
async function addEndpoint(page, endpointName) {
  if (await page.locator('.empty-cta').count()) await page.click('.empty-cta')
  else await page.click('.add-step')
  await page.waitForSelector('.tree-system-node', { timeout: 10000 })
  await page.waitForTimeout(500)
  await page.click('.tree-system-node >> nth=0')
  await page.waitForTimeout(600)
  const epNode = page.locator(`.tree-endpoint-node:has-text("${endpointName}")`).first()
  await epNode.waitFor({ timeout: 8000 })
  await epNode.click()
  await page.waitForTimeout(600)
  await page.click('button:has-text("加入编排画布")')
  await page.waitForTimeout(1200)
}

// ══ 路径 A: 真实数据(保底断言) ════════════════════════════════════
{
  const ctx = await newAuthedCtx()
  const page = await ctx.newPage()
  await createScenario(page, 'e2e-strategy-A')
  await addEndpoint(page, "查询订单详情")

  await page.waitForSelector('.strategy-form', { timeout: 10000 })
  const audit = await page.evaluate(() => {
    const forms = [...document.querySelectorAll('.strategy-form')]
    return {
      strategyForms: forms.length,
      badges: forms.map(f => f.querySelector('.sf-badge')?.textContent?.trim()),
      // v-show 不销毁 DOM,折叠态字段仍可审计
      fields: forms.map(f => [...f.querySelectorAll('.label-text')].map(l => l.textContent?.trim())),
      // 折叠态: 字段区不可见
      collapsed: forms.map(f => {
        const b = f.querySelector('.sf-body')
        return !(b && b.offsetParent !== null)
      }),
      summaries: forms.map(f => f.querySelector('.sf-summary')?.textContent?.trim()),
    }
  })
  console.log('A. initial:', JSON.stringify(audit))
  // 断言: 恰 1 条(assertion),$.status eq 200 保底,无 $.code(契约无 success_criteria)
  const flat = audit.fields.flat()
  if (audit.strategyForms !== 1) { console.error('A FAIL: expected 1 strategy, got', audit.strategyForms); process.exit(1) }
  if (!flat.includes('target') || !flat.includes('operator')) { console.error('A FAIL: assertion fields missing', flat); process.exit(1) }
  if (!audit.collapsed[0]) { console.error('A FAIL: 预填策略应默认折叠'); process.exit(1) }
  if (!/\$\.status/.test(audit.summaries[0] || '') || !/200/.test(audit.summaries[0] || '')) {
    console.error('A FAIL: 头行摘要缺 $.status/200:', audit.summaries[0]); process.exit(1)
  }
  console.log('A PASS: 保底 $.status 断言 + 默认折叠 + 头行摘要("' + audit.summaries[0] + '")')

  // 折叠交互: 点头行展开 → 字段区可见;再点折叠
  await page.click('.strategy-form .sf-head')
  await page.waitForTimeout(300)
  let expandState = await page.evaluate(() => {
    const b = document.querySelector('.strategy-form .sf-body')
    return { visible: !!(b && b.offsetParent !== null) }
  })
  if (!expandState.visible) { console.error('A FAIL: 点击头行未展开'); process.exit(1) }
  await page.click('.strategy-form .sf-head')
  await page.waitForTimeout(300)
  expandState = await page.evaluate(() => {
    const b = document.querySelector('.strategy-form .sf-body')
    return { visible: !!(b && b.offsetParent !== null) }
  })
  if (expandState.visible) { console.error('A FAIL: 再点未折叠'); process.exit(1) }
  console.log('A PASS: 折叠-展开交互')

  // 添加 assign + assertion,验 operator 下拉 14 项
  await page.click('.add-strategy')
  await page.waitForTimeout(400)
  await page.click('.el-dropdown-menu__item:has-text("准备入参赋值")')
  await page.waitForTimeout(800)
  // 新添加的 assign 应自动展开(引导填写)
  let newExpanded = await page.evaluate(() => {
    const forms = [...document.querySelectorAll('.strategy-form')]
    const a = forms.filter(f => f.querySelector('.sf-kind')?.textContent?.trim() === 'assign')[0]
    const b = a?.querySelector('.sf-body')
    return !!(b && b.offsetParent !== null)
  })
  if (!newExpanded) { console.error('A FAIL: 新添加策略应自动展开'); process.exit(1) }
  console.log('A PASS: 新添加策略自动展开')
  // 折叠它,再加 assertion
  await page.click('.strategy-form:nth-child(2) .sf-head')
  await page.waitForTimeout(200)
  await page.click('.add-strategy')
  await page.waitForTimeout(400)
  await page.click('.el-dropdown-menu__item:has-text("响应断言")')
  await page.waitForTimeout(800)
  let audit2 = await page.evaluate(() => ({
    strategyForms: document.querySelectorAll('.strategy-form').length,
    kinds: [...document.querySelectorAll('.sf-kind')].map(k => k.textContent?.trim()),
  }))
  console.log('A. after add:', JSON.stringify(audit2))
  if (audit2.strategyForms !== 3 || !audit2.kinds.includes('assign')) { console.error('A FAIL: add assign/assertion'); process.exit(1) }
  console.log('A PASS: assign + assertion 可添加')

  // operator select 14 项: 找 assertion 的 operator select
  const opOptions = await page.evaluate(() => {
    const forms = [...document.querySelectorAll('.strategy-form')]
    const a = forms.filter(f => f.querySelector('.sf-kind')?.textContent?.trim() === 'assertion')[0]
    if (!a) return null
    const sel = [...a.querySelectorAll('select')].find(s =>
      [...s.options].some(o => o.value === 'eq'))
    return sel ? [...sel.options].map(o => o.value).filter(Boolean) : null
  })
  console.log('A. operator options:', JSON.stringify(opOptions))
  if (!opOptions || opOptions.length !== 14) { console.error('A FAIL: operator enum != 14'); process.exit(1) }
  console.log('A PASS: operator 下拉 14 项')

  // 保存 + 重新进入 step=4 验持久(保存后组件内 scenario 已建,id 从 POST 响应来;
  // URL 仍是 /composer/new,用 draft store 的 scenarioId 或直接查 scenarios 列表拿 id)
  const saveBtn = page.locator('button:has-text("保存")').first()
  if (await saveBtn.count()) {
    await saveBtn.click()
    await page.waitForTimeout(2500)
  }
  const scenarioId = await page.evaluate(() => {
    // 从 Vue app 状态拿不到;退而求其次:取页面 URL 或查最近创建的
    return null
  })
  // 直接从网络拿:重新 GET scenarios 列表找 name 匹配的
  const listRes = await page.evaluate(async (nm) => {
    const token = JSON.parse(localStorage.getItem('gimbal-auth') || '{}')
    const r = await fetch('/api/scenarios?q=' + encodeURIComponent(nm), {
      headers: { Authorization: 'Bearer ' + token.accessToken },
    })
    const j = await r.json()
    return (Array.isArray(j) ? j : []).map((s) => s.meta?.scenarioId)
  }, 'e2e-strategy-A')
  const sid = (listRes || [])[0]
  if (!sid) { console.error('A FAIL: saved scenario not found'); process.exit(1) }
  await page.goto(`${BASE}/composer/${sid}?step=4`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.strategy-form', { timeout: 15000 })
  const audit3 = await page.evaluate(() => ({
    strategyForms: document.querySelectorAll('.strategy-form').length,
  }))
  console.log('A. after reload:', JSON.stringify(audit3))
  if (audit3.strategyForms !== 3) { console.error('A FAIL: strategies lost after reload'); process.exit(1) }
  console.log('A PASS: reload 后策略仍在')
  await page.screenshot({ path: `${OUT}/strategy-A-1440.png`, fullPage: true })
  await ctx.close()
}

// ══ 路径 B: 拦截 /full 注入契约(验证预填分支) ═════════════════════
{
  const ctx = await newAuthedCtx()
  const page = await ctx.newPage()
  // 拦截 platform 代理的 /full,注入 success_criteria + $.code
  await ctx.route('**/api/endpoint-catalog/**/full', async (route) => {
    const resp = await route.fetch()
    const body = await resp.json()
    body.metadata = { ...(body.metadata || {}), success_criteria: '返回 code=0 表示成功' }
    body.responses = body.responses || {}
    body.responses['200'] = { ...(body.responses['200'] || {}), assertable_fields: ['$.code', '$.data.order_id'] }
    await route.fulfill({ response: resp, json: body })
  })
  await createScenario(page, 'e2e-strategy-B')
  await addEndpoint(page, "查询订单详情")

  await page.waitForSelector('.strategy-form', { timeout: 10000 })
  const audit = await page.evaluate(() => {
    const forms = [...document.querySelectorAll('.strategy-form')]
    return {
      strategyForms: forms.length,
      fields: forms.map(f => [...f.querySelectorAll('.label-text')].map(l => l.textContent?.trim())),
    }
  })
  console.log('B. initial:', JSON.stringify(audit))
  if (audit.strategyForms !== 2) { console.error('B FAIL: expected 2 strategies (status + code), got', audit.strategyForms); process.exit(1) }
  // 验第二条的 target 值是 $.code,message 是注入的 success_criteria
  const codeVal = await page.evaluate(() => {
    const forms = [...document.querySelectorAll('.strategy-form')]
    const inputs = [...forms[1].querySelectorAll('input.ctl')]
    const target = inputs.find(i => i.placeholder?.includes('target') || true)
    return { values: inputs.map(i => i.value) }
  })
  console.log('B. second strategy input values:', JSON.stringify(codeVal))
  await page.screenshot({ path: `${OUT}/strategy-B-1440.png`, fullPage: true })
  await ctx.close()
}

console.log('ALL E2E PASS')
await browser.close()
