/**
 * U6.2：柯利/边境牧羊犬双候选提示的真实页面验收（Playwright + 系统 Chrome）。
 *
 * 用法（在仓库根目录执行）::
 *
 *   node scripts/page_accept_collie_pair.mjs --scenario on
 *   node scripts/page_accept_collie_pair.mjs --scenario off
 *
 * ``on`` ：后端开启候选功能（默认）。上传真实触发图，核验两项候选中文名、
 *          组内得分和约 100%、原始 Top-K 不变、用户选择独立显示；
 *          上传不触发图与非目标犬种，确认候选区不出现。
 * ``off``：关闭候选功能后复测同一张图，确认恢复原有显示行为。
 *
 * 只读 validation 图片；截图写入 reports/u6_2_collie_pair_candidate/screenshots/。
 */
import { mkdirSync, writeFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// ESM 不认 NODE_PATH；用 createRequire 从绝对路径解析 Playwright，
// 这样它装在仓库外的临时目录也能被加载，不必写进 frontend/package.json。
const require = createRequire(import.meta.url)
const playwrightEntry = process.env.PW_PATH || 'playwright'
const { chromium } = require(playwrightEntry)

const here = dirname(fileURLToPath(import.meta.url))
const REPO = resolve(here, '..')
const OUT = resolve(REPO, 'reports/u6_2_collie_pair_candidate')
const SHOTS = resolve(OUT, 'screenshots')
const BASE_URL = 'http://127.0.0.1:5173/predict'

const VAL = resolve(REPO, 'data/v2_processed/val')

const SAMPLES = {
  // 真实触发图（Top-1 = border_collie，margin 0.2017）
  triggerA: resolve(VAL, 'border_collie/n02106166_416.jpg'),
  // 真实触发图（Top-1 = collie，margin 0.2078）—— 模型把边牧判成柯利
  triggerB: resolve(VAL, 'border_collie/n02106166_549.jpg'),
  // 真实触发图（Top-1 = border_collie，margin 0.2525）
  triggerC: resolve(VAL, 'border_collie/n02106166_884.jpg'),
  // 不触发图（Top-1 = collie，但 margin 0.6299 > 0.30）
  nonTrigger: resolve(VAL, 'afghan_hound/n02088094_1479.jpg'),
  // 非目标犬种（取目录下第一张）
  beagle: resolve(VAL, 'beagle'),
}

const checks = []
function record(name, passed, detail = '') {
  checks.push({ check: name, passed: Boolean(passed), detail })
  console.log(`  [${passed ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`)
}

async function waitReady(page) {
  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForSelector('input[type="file"]', { state: 'attached', timeout: 20000 })
}

async function uploadAndPredict(page, imagePath) {
  const reset = page.getByRole('button', { name: '一键清空' })
  if (await reset.isEnabled().catch(() => false)) {
    await reset.click()
    await page.waitForTimeout(300)
  }
  await page.setInputFiles('input[type="file"]', imagePath)
  await page.waitForTimeout(500)
  await page.getByRole('button', { name: '开始识别' }).click()
  await page.waitForSelector('.prediction-result', { timeout: 30000 })
  await page.waitForTimeout(900)
}

async function readResult(page) {
  return page.evaluate(() => {
    const text = (el) => (el ? el.textContent.trim().replace(/\s+/g, ' ') : null)
    return {
      hasCandidateBlock: Boolean(document.querySelector('.candidate-block')),
      groupId: document.querySelector('.candidate-group-id')?.dataset.groupId ?? null,
      subtitle: text(document.querySelector('.candidate-subtitle')),
      candidates: [...document.querySelectorAll('.candidate-row')].map((row) => ({
        name: text(row.querySelector('.candidate-name')),
        scoreText: text(row.querySelector('.candidate-score-value')),
        rawText: text(row.querySelector('.candidate-raw')),
      })),
      radioCount: document.querySelectorAll('.candidate-block .el-radio').length,
      topk: [...document.querySelectorAll('.prediction-row')].map((row) => ({
        breed: text(row.querySelector('.prediction-breed')),
        scoreText: text(row.querySelector('.score-value')),
      })),
      userChoice: document.querySelector('.user-choice')
        ? {
            value: text(document.querySelector('.user-choice-value')),
            hint: text(document.querySelector('.user-choice-hint')),
          }
        : null,
      bodyText: document.body.innerText,
    }
  })
}

const parseScore = (value) => {
  const match = String(value || '').match(/([\d.]+)\s*%/)
  return match ? Number(match[1]) : NaN
}

const sumScores = (snap) => snap.candidates
  .map((c) => parseScore(c.scoreText))
  .reduce((a, b) => a + b, 0)

async function scenarioOn(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const evidence = {}

  console.log('\n=== 场景 1：真实触发图 A（Top-1=border_collie）===')
  await waitReady(page)
  await uploadAndPredict(page, SAMPLES.triggerA)
  const snapA = await readResult(page)
  evidence.triggerA = snapA
  await page.screenshot({ path: resolve(SHOTS, '01_collie_pair_trigger_A.png'), fullPage: true })

  record('1: 双候选区出现', snapA.hasCandidateBlock)
  record('1: 组标识为 collie-pair', snapA.groupId === 'collie-pair', snapA.groupId)
  record('1: 候选行为 2', snapA.candidates.length === 2, `实际 ${snapA.candidates.length}`)
  const namesA = snapA.candidates.map((c) => c.name).sort()
  record('1: 两个候选中文名正确',
    JSON.stringify(namesA) === JSON.stringify(['柯利牧羊犬', '边境牧羊犬']),
    JSON.stringify(namesA))
  record('1: 副标题如实说明是这两个牧羊犬难以区分',
    (snapA.subtitle || '').includes('柯利牧羊犬')
    && (snapA.subtitle || '').includes('边境牧羊犬'),
    snapA.subtitle)
  record('1: 组内得分和约 100%', Math.abs(sumScores(snapA) - 100) <= 0.05,
    `sum=${sumScores(snapA).toFixed(4)}`)
  record('1: 原始 Top-K 仍为 3 行', snapA.topk.length === 3, `实际 ${snapA.topk.length}`)
  record('1: 原始 Top-1 为中文犬种名',
    (snapA.topk[0]?.breed || '').includes('牧羊犬'), snapA.topk[0]?.breed)
  record('1: 图例标注"候选组内相对得分"且含 collie-pair 版本',
    (snapA.bodyText || '').includes('候选组内相对得分')
    && (snapA.bodyText || '').includes('val-2026-10-21-collie-pair-v1'))

  console.log('\n=== 场景 2：真实触发图 B（Top-1=collie，模型把边牧判成柯利）===')
  await uploadAndPredict(page, SAMPLES.triggerB)
  const snapB = await readResult(page)
  evidence.triggerB = snapB
  await page.screenshot({ path: resolve(SHOTS, '02_collie_pair_trigger_B.png'), fullPage: true })
  record('2: 双候选区出现', snapB.hasCandidateBlock)
  record('2: 候选行为 2', snapB.candidates.length === 2)
  record('2: 组内得分和约 100%', Math.abs(sumScores(snapB) - 100) <= 0.05,
    `sum=${sumScores(snapB).toFixed(4)}`)
  record('2: 原始 Top-1 为"柯利牧羊犬"',
    (snapB.topk[0]?.breed || '') === '柯利牧羊犬', snapB.topk[0]?.breed)

  console.log('\n=== 场景 3：用户选择独立显示 ===')
  await page.locator('.candidate-block .el-radio').nth(1).click()
  await page.waitForTimeout(400)
  const snapC = await readResult(page)
  evidence.userSelection = snapC
  await page.screenshot({ path: resolve(SHOTS, '03_user_selection.png'), fullPage: true })
  record('3: "你选择的品种"出现', Boolean(snapC.userChoice))
  record('3: 选择值等于第 2 个候选',
    snapC.userChoice?.value === snapC.candidates[1]?.name,
    `${snapC.userChoice?.value} vs ${snapC.candidates[1]?.name}`)
  record('3: 提示模型首选未被替换',
    (snapC.userChoice?.hint || '').includes('未被替换'), snapC.userChoice?.hint)
  record('3: 用户选择后原始 Top-K 未变',
    JSON.stringify(snapC.topk) === JSON.stringify(snapB.topk))

  console.log('\n=== 场景 4：真实触发图 C ===')
  await uploadAndPredict(page, SAMPLES.triggerC)
  const snapD = await readResult(page)
  evidence.triggerC = snapD
  await page.screenshot({ path: resolve(SHOTS, '04_collie_pair_trigger_C.png'), fullPage: true })
  record('4: 双候选区出现', snapD.hasCandidateBlock)
  record('4: 候选行为 2', snapD.candidates.length === 2)
  record('4: 组内得分和约 100%', Math.abs(sumScores(snapD) - 100) <= 0.05,
    `sum=${sumScores(snapD).toFixed(4)}`)

  console.log('\n=== 场景 5：不触发图（Top-1=collie 但分差过大）===')
  await uploadAndPredict(page, SAMPLES.nonTrigger)
  const snapE = await readResult(page)
  evidence.nonTrigger = snapE
  await page.screenshot({ path: resolve(SHOTS, '05_non_trigger.png'), fullPage: true })
  record('5: 候选区完全不出现', snapE.hasCandidateBlock === false)
  record('5: "你选择的品种"不出现', snapE.userChoice === null)
  record('5: 原始 Top-K 正常显示 3 行', snapE.topk.length === 3)
  record('5: 原始 Top-1 为"柯利牧羊犬"',
    (snapE.topk[0]?.breed || '') === '柯利牧羊犬', snapE.topk[0]?.breed)

  console.log('\n=== 场景 6：非目标犬种 ===')
  const beagleFile = resolve(SAMPLES.beagle,
    readdirSync(SAMPLES.beagle).find((f) => f.endsWith('.jpg')))
  await uploadAndPredict(page, beagleFile)
  const snapF = await readResult(page)
  evidence.beagle = snapF
  await page.screenshot({ path: resolve(SHOTS, '06_non_target_breed.png'), fullPage: true })
  record('6: 非目标犬种候选区不出现', snapF.hasCandidateBlock === false)
  record('6: 非目标犬种 Top-1 为"比格犬"',
    (snapF.topk[0]?.breed || '') === '比格犬', snapF.topk[0]?.breed)

  console.log('\n=== 场景 7：文案不暗示必然有正确答案 ===')
  record('7: 声明"不保证候选中一定包含正确品种"',
    (snapA.bodyText || '').includes('不保证候选中一定包含正确品种'))
  record('7: 不含"其中必有一个/必然/一定是"',
    !(snapA.bodyText || '').includes('其中必有一个')
    && !(snapA.bodyText || '').includes('必然')
    && !(snapA.bodyText || '').includes('一定是'))

  await page.close()
  return evidence
}

async function scenarioOff(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  console.log('\n=== 场景 8：关闭候选功能后复测同一张图 ===')
  await waitReady(page)
  await uploadAndPredict(page, SAMPLES.triggerA)
  const snap = await readResult(page)
  await page.screenshot({ path: resolve(SHOTS, '07_switch_off.png'), fullPage: true })

  record('8: 候选区消失', snap.hasCandidateBlock === false)
  record('8: "你选择的品种"不出现', snap.userChoice === null)
  record('8: 原始 Top-K 仍为 3 行', snap.topk.length === 3)
  record('8: 原始 Top-1 仍为"边境牧羊犬"',
    (snap.topk[0]?.breed || '') === '边境牧羊犬', snap.topk[0]?.breed)

  await page.close()
  return { switchOff: snap }
}

async function main() {
  const scenario = process.argv.includes('--scenario')
    ? process.argv[process.argv.indexOf('--scenario') + 1]
    : 'on'

  mkdirSync(SHOTS, { recursive: true })
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  console.log(`[page] Chrome launched, scenario = ${scenario}`)

  let evidence
  try {
    evidence = scenario === 'off'
      ? await scenarioOff(browser)
      : await scenarioOn(browser)
  } finally {
    await browser.close()
  }

  const passed = checks.filter((c) => c.passed).length
  const failed = checks.filter((c) => !c.passed)
  console.log(`\n[page] ${passed}/${checks.length} 项通过，失败 ${failed.length} 项`)
  for (const item of failed) console.log(`    FAIL: ${item.check} — ${item.detail}`)

  const outPath = resolve(OUT, `page_acceptance_${scenario}.json`)
  writeFileSync(outPath, JSON.stringify({
    scenario,
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    samples: SAMPLES,
    checks,
    passed,
    total: checks.length,
    evidence,
  }, null, 2), 'utf-8')
  console.log(`[page] wrote ${outPath}`)

  process.exit(failed.length === 0 ? 0 : 2)
}

main().catch((error) => {
  console.error('[page] fatal:', error)
  process.exit(1)
})
