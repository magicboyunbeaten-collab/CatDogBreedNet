/**
 * U5.5：V2.1 接入后的真实浏览器验收（Playwright + 系统 Chrome）。
 *
 * 用法（在仓库根目录执行）::
 *
 *   node scripts/page_accept_v2_1_integration.mjs --scenario on
 *   node scripts/page_accept_v2_1_integration.mjs --scenario off
 *
 * ``on`` ：后端默认配置（V2.1 + 四类候选默认开启）—— 验证
 *          ① APBT/AmStaff 竞争样本的四类候选区；
 *          ② APBT 为 Top-1 时候选含 APBT 且原始 Top-K 不变；
 *          ③ 用户选择独立呈现、不覆盖模型预测；
 *          ④ 非候选组猫图不出现候选区；
 *          ⑤ 136 类中文名生效（界面不出现英文下划线标签）。
 * ``off`` ：`CATDOG_CANDIDATE_GROUP_ENABLED=false` 重启后端后复测同一张图 ——
 *          候选区消失、原始 Top-K 不变。
 *
 * 只读 validation 图片；只写本报告目录下的截图与证据 JSON。
 */
import { mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PW_PATH || 'playwright')

const here = dirname(fileURLToPath(import.meta.url))
const REPO = resolve(here, '..')
const OUT = resolve(REPO, 'reports/u5_5_v2_1_integration')
const SHOTS = resolve(OUT, 'screenshots')
const BASE_URL = 'http://127.0.0.1:5173/predict'

const VAL = resolve(REPO, 'data/v2_processed/val')
const SAMPLES = {
  // Top-1 = AmStaff，与 APBT 强竞争（margin ≈ 0.07）→ 四类候选触发
  competition: resolve(VAL, 'american_pit_bull_terrier/american_pit_bull_terrier_11.jpg'),
  // Top-1 = APBT（margin ≈ 0.077）→ 候选组含 APBT
  apbtTop1: resolve(VAL, 'american_pit_bull_terrier/american_pit_bull_terrier_132.jpg'),
  // Top-1 = SBT 的 val 触发样本
  sbtTop1: resolve(VAL, 'staffordshire_bull_terrier/staffordshire_bull_terrier_160.jpg'),
  // 非候选组（猫）
  cat: resolve(VAL, 'Abyssinian/Abyssinian_10.jpg'),
}

const EXPECTED_ZH = [
  '美国比特斗牛梗',
  '美国斯塔福郡梗',
  '斯塔福郡斗牛梗',
  '美国斗牛犬',
]

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
      legend: text(document.querySelector('.candidate-legend')),
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

async function scenarioOn(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const evidence = {}

  // ---------- 场景 1：APBT/AmStaff 竞争 ----------
  console.log('\n=== 场景 1：APBT / AmStaff 竞争样本 ===')
  await waitReady(page)
  await uploadAndPredict(page, SAMPLES.competition)
  const snapA = await readResult(page)
  evidence.competition = snapA
  await page.screenshot({ path: resolve(SHOTS, '01_competition_four_candidates.png'), fullPage: true })

  record('1: 四类候选区出现', snapA.hasCandidateBlock)
  record('1: 候选行为 4', snapA.candidates.length === 4, `实际 ${snapA.candidates.length}`)
  const namesA = snapA.candidates.map((c) => c.name).sort()
  record('1: 四个候选中文名与候选面板一致',
    JSON.stringify(namesA) === JSON.stringify([...EXPECTED_ZH].sort()),
    JSON.stringify(namesA))
  const sumA = snapA.candidates.map((c) => parseScore(c.scoreText))
    .reduce((a, b) => a + b, 0)
  record('1: 组内得分和 ≈ 100%', Math.abs(sumA - 100) <= 0.05, `sum=${sumA.toFixed(4)}`)
  record('1: 标注"候选组内相对得分"', (snapA.legend || '').includes('候选组内相对得分'))
  record('1: 原始 Top-K 仍为 3 行', snapA.topk.length === 3, `实际 ${snapA.topk.length}`)
  record('1: 原始 Top-1 为中文（非英文下划线）',
    (snapA.topk[0]?.breed || '').includes('斯塔福郡梗')
    && !(snapA.topk[0]?.breed || '').includes('_'),
    snapA.topk[0]?.breed)

  // ---------- 场景 2：APBT 为 Top-1 ----------
  console.log('\n=== 场景 2：APBT 为 Top-1 ===')
  await uploadAndPredict(page, SAMPLES.apbtTop1)
  const snapB = await readResult(page)
  evidence.apbtTop1 = snapB
  await page.screenshot({ path: resolve(SHOTS, '02_apbt_top1.png'), fullPage: true })

  record('2: 四类候选区出现', snapB.hasCandidateBlock)
  record('2: 候选含"美国比特斗牛梗"',
    snapB.candidates.some((c) => c.name === '美国比特斗牛梗'))
  record('2: 原始 Top-1 为"美国比特斗牛梗"（中文）',
    (snapB.topk[0]?.breed || '') === '美国比特斗牛梗', snapB.topk[0]?.breed)
  record('2: 原始 Top-1 分数仍为原始百分比',
    /%$/.test(snapB.topk[0]?.scoreText || ''), snapB.topk[0]?.scoreText)

  // ---------- 场景 3：用户选择 ----------
  console.log('\n=== 场景 3：用户选择独立呈现 ===')
  await page.locator('.candidate-block .el-radio').nth(1).click()
  await page.waitForTimeout(400)
  const snapC = await readResult(page)
  evidence.userSelection = snapC
  await page.screenshot({ path: resolve(SHOTS, '03_user_selection.png'), fullPage: true })

  record('3: "你选择的品种"出现', Boolean(snapC.userChoice))
  record('3: 选择值等于第 2 个候选',
    snapC.userChoice?.value === snapC.candidates[1]?.name,
    `${snapC.userChoice?.value} vs ${snapC.candidates[1]?.name}`)
  record('3: 提示"模型首选仍为 … 未被替换"',
    (snapC.userChoice?.hint || '').includes('未被替换'), snapC.userChoice?.hint)
  record('3: 用户选择后原始 Top-K 未变',
    JSON.stringify(snapC.topk) === JSON.stringify(snapB.topk))

  // ---------- 场景 4：SBT 为 Top-1 ----------
  console.log('\n=== 场景 4：SBT 为 Top-1 ===')
  await uploadAndPredict(page, SAMPLES.sbtTop1)
  const snapD = await readResult(page)
  evidence.sbtTop1 = snapD
  await page.screenshot({ path: resolve(SHOTS, '04_sbt_top1.png'), fullPage: true })

  record('4: 四类候选区出现', snapD.hasCandidateBlock)
  record('4: 原始 Top-1 为"斯塔福郡斗牛梗"',
    (snapD.topk[0]?.breed || '') === '斯塔福郡斗牛梗', snapD.topk[0]?.breed)
  const sumD = snapD.candidates.map((c) => parseScore(c.scoreText))
    .reduce((a, b) => a + b, 0)
  record('4: 组内得分和 ≈ 100%', Math.abs(sumD - 100) <= 0.05, `sum=${sumD.toFixed(4)}`)

  // ---------- 场景 5：非候选组猫 ----------
  console.log('\n=== 场景 5：非候选组猫图 ===')
  await uploadAndPredict(page, SAMPLES.cat)
  const snapE = await readResult(page)
  evidence.nonCandidate = snapE
  await page.screenshot({ path: resolve(SHOTS, '05_non_candidate.png'), fullPage: true })

  record('5: 候选区完全不出现', snapE.hasCandidateBlock === false)
  record('5: "你选择的品种"不出现', snapE.userChoice === null)
  record('5: 原始 Top-K 正常显示 3 行', snapE.topk.length === 3)
  record('5: 猫类别显示中文"阿比西尼亚猫"',
    (snapE.topk[0]?.breed || '') === '阿比西尼亚猫', snapE.topk[0]?.breed)

  // ---------- 场景 6：136 类中文名生效 ----------
  console.log('\n=== 场景 6：136 类中文名生效（无英文下划线主标签）===')
  const allSnaps = [snapA, snapB, snapD, snapE]
  const underscoreLabels = allSnaps.flatMap((s) => s.topk)
    .map((r) => r.breed)
    .filter((b) => b && b.includes('_'))
  record('6: 所有 Top-K 主标签均无英文下划线', underscoreLabels.length === 0,
    JSON.stringify(underscoreLabels))

  await page.close()
  return evidence
}

async function scenarioOff(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  console.log('\n=== 场景 7：关闭候选开关后复测 ===')
  await waitReady(page)
  await uploadAndPredict(page, SAMPLES.apbtTop1)
  const snap = await readResult(page)
  await page.screenshot({ path: resolve(SHOTS, '06_switch_off.png'), fullPage: true })

  record('7: 候选区消失', snap.hasCandidateBlock === false)
  record('7: "你选择的品种"不出现', snap.userChoice === null)
  record('7: 原始 Top-K 仍为 3 行', snap.topk.length === 3)
  record('7: 原始 Top-1 仍为"美国比特斗牛梗"（预测不受开关影响）',
    (snap.topk[0]?.breed || '') === '美国比特斗牛梗', snap.topk[0]?.breed)

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
