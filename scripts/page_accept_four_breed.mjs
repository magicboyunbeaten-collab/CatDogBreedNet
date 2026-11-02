/**
 * U5.3 四类相近犬种候选 —— 真实浏览器页面验收
 *
 * 用 Playwright 驱动**系统已安装的 Chrome**（channel: 'chrome'，无需下载
 * chromium），打开真实 Vite 前端页面，上传 validation 图片，逐场景断言并截图。
 *
 * 用法（在仓库根目录执行）::
 *
 *   node scripts/page_accept_four_breed.mjs --scenario on
 *   node scripts/page_accept_four_breed.mjs --scenario off
 *
 * ``on``  ：后端候选组开启 —— 验证四类候选展示、得分归一化、Top-K 不变、
 *           用户选择独立呈现、非候选图不展示候选区。
 * ``off`` ：后端候选组关闭 —— 验证同一张触发图不再展示候选区（恢复原行为）。
 *
 * 只读 validation 图片，只写报告目录下的截图与证据 JSON。
 */
import { mkdirSync, writeFileSync } from 'node:fs'
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
const OUT = resolve(REPO, 'reports/v2_1_four_breed_page_acceptance')
const SHOTS = resolve(OUT, 'screenshots')
const BASE_URL = 'http://127.0.0.1:5173/predict'

const VAL = resolve(REPO, 'data/v2_processed/val')
const SAMPLES = {
  // Top-1 = APBT，四类触发（证明 APBT 出现在候选区）
  triggerApbt: resolve(VAL, 'american_pit_bull_terrier/american_pit_bull_terrier_132.jpg'),
  // Top-1 = AmStaff，四类触发
  triggerAmstaff: resolve(VAL, 'american_pit_bull_terrier/american_pit_bull_terrier_11.jpg'),
  // 非候选组（猫），不应出现候选区
  nonCandidate: resolve(VAL, 'Abyssinian/Abyssinian_10.jpg'),
}

const EXPECTED_ZH = {
  american_pit_bull_terrier: '美国比特斗牛梗',
  american_staffordshire_terrier: '美国斯塔福郡梗',
  staffordshire_bull_terrier: '斯塔福郡斗牛梗',
  american_bulldog: '美国斗牛犬',
}

const checks = []
function record(name, passed, detail = '') {
  checks.push({ check: name, passed: Boolean(passed), detail })
  console.log(`  [${passed ? 'PASS' : 'FAIL'}] ${name}${detail ? ' — ' + detail : ''}`)
}

/** 等待页面就绪（而非固定 sleep）。 */
async function waitReady(page) {
  await page.goto(BASE_URL, { waitUntil: 'networkidle', timeout: 30000 })
  await page.waitForSelector('input[type="file"]', { state: 'attached', timeout: 20000 })
}

/** 上传一张图并等待识别结果渲染。 */
async function uploadAndPredict(page, imagePath) {
  // 重置：若已有结果，先点"一键清空"
  const reset = page.getByRole('button', { name: '一键清空' })
  if (await reset.isEnabled().catch(() => false)) {
    await reset.click()
    await page.waitForTimeout(300)
  }
  await page.setInputFiles('input[type="file"]', imagePath)
  await page.waitForTimeout(500)
  await page.getByRole('button', { name: '开始识别' }).click()
  await page.waitForSelector('.prediction-result', { timeout: 30000 })
  // 等候选区是否出现（最多 2s），避免竞态
  await page.waitForTimeout(900)
}

/** 读取当前页面的结构化结果。 */
async function readResult(page) {
  return page.evaluate(() => {
    const text = (el) => (el ? el.textContent.trim().replace(/\s+/g, ' ') : null)
    const topk = [...document.querySelectorAll('.prediction-row')].map((row) => ({
      rank: text(row.querySelector('.prediction-rank')),
      breed: text(row.querySelector('.prediction-breed')),
      scoreText: text(row.querySelector('.score-value')),
    }))
    const candidateBlock = document.querySelector('.candidate-block')
    const candidates = [...document.querySelectorAll('.candidate-row')].map((row) => ({
      name: text(row.querySelector('.candidate-name')),
      scoreText: text(row.querySelector('.candidate-score-value')),
      rawText: text(row.querySelector('.candidate-raw')),
      isModelTop: row.classList.contains('is-model-top'),
    }))
    const userChoice = document.querySelector('.user-choice')
    return {
      hasCandidateBlock: Boolean(candidateBlock),
      candidateTitle: text(document.querySelector('.candidate-title')),
      candidateSubtitle: text(document.querySelector('.candidate-subtitle')),
      legend: text(document.querySelector('.candidate-legend')),
      note: text(document.querySelector('.candidate-note')),
      candidates,
      radioCount: document.querySelectorAll('.candidate-block .el-radio').length,
      topk,
      userChoice: userChoice
        ? {
            label: text(userChoice.querySelector('.user-choice-label')),
            value: text(userChoice.querySelector('.user-choice-value')),
            hint: text(userChoice.querySelector('.user-choice-hint')),
          }
        : null,
      resultNote: text(document.querySelector('.result-note')),
    }
  })
}

const parseScore = (value) => {
  if (!value) return NaN
  const match = String(value).match(/([\d.]+)\s*%/)
  return match ? Number(match[1]) : NaN
}

async function scenarioOn(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  const evidence = {}

  // ---------- 场景 1：触发图 A（Top-1 = APBT）----------
  console.log('\n=== 场景 1：触发图 A（Top-1 = APBT）===')
  await waitReady(page)
  await uploadAndPredict(page, SAMPLES.triggerApbt)
  let snap = await readResult(page)
  evidence.triggerApbt = snap
  await page.screenshot({ path: resolve(SHOTS, '01_trigger_apbt.png'), fullPage: true })

  record('候选区出现', snap.hasCandidateBlock)
  record('候选区标题为"外观相近的候选品种"',
    snap.candidateTitle === '外观相近的候选品种', snap.candidateTitle)
  record('候选行数量为 4', snap.candidates.length === 4,
    `实际 ${snap.candidates.length}`)
  record('单选按钮数量为 4', snap.radioCount === 4, `实际 ${snap.radioCount}`)

  const names = snap.candidates.map((c) => c.name)
  const expectedNames = Object.values(EXPECTED_ZH)
  record('四个中文名齐全且正确',
    expectedNames.every((n) => names.includes(n)),
    `实际 ${JSON.stringify(names)}`)

  const scores = snap.candidates.map((c) => parseScore(c.scoreText))
  const sum = scores.reduce((a, b) => a + b, 0)
  record('组内相对得分之和 ≈ 100%',
    Number.isFinite(sum) && Math.abs(sum - 100) <= 0.05,
    `sum=${sum.toFixed(4)}`)
  record('得分标注为"候选组内相对得分"',
    (snap.legend || '').includes('候选组内相对得分'), snap.legend)
  record('标注"不是整体识别置信度/真实概率/准确率"',
    (snap.legend || '').includes('不是'), snap.legend)
  // 图例文案里的候选数量必须与实际展示的四项一致（不得残留"三个"）
  const NUM_ZH = ['零', '一', '两', '三', '四', '五', '六']
  const statedCount = (legend) => {
    const match = String(legend || '').match(/([0-9]+|[一二两三四五六])\s*个候选/)
    if (!match) return NaN
    const raw = match[1]
    return /^[0-9]+$/.test(raw) ? Number(raw) : NUM_ZH.indexOf(raw)
  }
  record('图例候选数量表述与实际一致',
    statedCount(snap.legend) === snap.candidates.length,
    `图例声明 ${statedCount(snap.legend)} 个 / 实际 ${snap.candidates.length} 个`)
  record('图例不残留"三个候选"表述',
    !(snap.legend || '').includes('三个候选'), snap.legend)

  record('原始 Top-K 仍为 3 行', snap.topk.length === 3, `实际 ${snap.topk.length}`)
  record('Top-1 为 APBT（模型首选未被替换）',
    (snap.topk[0]?.breed || '').includes('比特斗牛梗'), snap.topk[0]?.breed)
  record('Top-1 分数仍显示原始百分比',
    /%$/.test(snap.topk[0]?.scoreText || ''), snap.topk[0]?.scoreText)
  record('提示语含"登记品种"', (snap.note || '').includes('登记品种'))
  record('提示语不暗示必有正确答案',
    !/(其中必有一个|必然|一定是)/.test(JSON.stringify(snap)))

  // ---------- 场景 2：用户选择交互 ----------
  console.log('\n=== 场景 2：用户选择交互 ===')
  record('默认已显示"你选择的品种"区块', Boolean(snap.userChoice),
    snap.userChoice?.label)
  record('默认选择为模型首选',
    Boolean(snap.userChoice) && snap.candidates[0]?.isModelTop,
    `model-top=${snap.candidates[0]?.isModelTop}`)

  // 点击第 2 个候选的单选按钮
  await page.locator('.candidate-block .el-radio').nth(1).click()
  await page.waitForTimeout(400)
  const afterClick = await readResult(page)
  evidence.userSelection = afterClick
  await page.screenshot({ path: resolve(SHOTS, '03_user_selection.png'), fullPage: true })

  record('用户选择后"你选择的品种"仍存在', Boolean(afterClick.userChoice))
  record('用户选择值变为第 2 个候选',
    afterClick.userChoice?.value === afterClick.candidates[1]?.name,
    `${afterClick.userChoice?.value} vs ${afterClick.candidates[1]?.name}`)
  record('提示说明"模型首选仍为 … 未被替换"',
    (afterClick.userChoice?.hint || '').includes('未被替换'),
    afterClick.userChoice?.hint)
  record('用户选择后原始 Top-1 未被替换',
    afterClick.topk[0]?.breed === snap.topk[0]?.breed,
    `${afterClick.topk[0]?.breed} vs ${snap.topk[0]?.breed}`)
  record('用户选择后原始 Top-1 分数未变',
    afterClick.topk[0]?.scoreText === snap.topk[0]?.scoreText,
    `${afterClick.topk[0]?.scoreText} vs ${snap.topk[0]?.scoreText}`)
  record('用户选择后候选区得分未变',
    JSON.stringify(afterClick.candidates.map((c) => c.scoreText))
      === JSON.stringify(snap.candidates.map((c) => c.scoreText)))

  // ---------- 场景 3：触发图 B（Top-1 = AmStaff）----------
  console.log('\n=== 场景 3：触发图 B（Top-1 = AmStaff）===')
  await uploadAndPredict(page, SAMPLES.triggerAmstaff)
  const snapB = await readResult(page)
  evidence.triggerAmstaff = snapB
  await page.screenshot({ path: resolve(SHOTS, '02_trigger_amstaff.png'), fullPage: true })

  record('候选区出现', snapB.hasCandidateBlock)
  record('候选行数量为 4', snapB.candidates.length === 4,
    `实际 ${snapB.candidates.length}`)
  const scoresB = snapB.candidates.map((c) => parseScore(c.scoreText))
  const sumB = scoresB.reduce((a, b) => a + b, 0)
  record('组内相对得分之和 ≈ 100%',
    Number.isFinite(sumB) && Math.abs(sumB - 100) <= 0.05,
    `sum=${sumB.toFixed(4)}`)
  record('Top-1 为 AmStaff（与 A 不同，说明结果随图片变化）',
    (snapB.topk[0]?.breed || '').includes('斯塔福郡梗')
    && snapB.topk[0]?.breed !== snap.topk[0]?.breed,
    `${snapB.topk[0]?.breed}`)

  // ---------- 场景 4：非候选组图片 ----------
  console.log('\n=== 场景 4：非候选组图片（猫）===')
  await uploadAndPredict(page, SAMPLES.nonCandidate)
  const snapC = await readResult(page)
  evidence.nonCandidate = snapC
  await page.screenshot({ path: resolve(SHOTS, '04_non_candidate.png'), fullPage: true })

  record('候选区完全不出现', snapC.hasCandidateBlock === false)
  record('"你选择的品种"区块不出现', snapC.userChoice === null)
  record('原始 Top-K 仍正常显示', snapC.topk.length === 3,
    `实际 ${snapC.topk.length}`)

  await page.close()
  return evidence
}

async function scenarioOff(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
  console.log('\n=== 场景 5：关闭 CATDOG_CANDIDATE_GROUP_ENABLED 后复测 ===')
  await waitReady(page)
  await uploadAndPredict(page, SAMPLES.triggerApbt)
  const snap = await readResult(page)
  await page.screenshot({ path: resolve(SHOTS, '05_switch_off.png'), fullPage: true })

  record('同一张触发图不再展示候选区', snap.hasCandidateBlock === false)
  record('无"你选择的品种"区块', snap.userChoice === null)
  record('原始 Top-K 仍正常显示（3 行）', snap.topk.length === 3,
    `实际 ${snap.topk.length}`)
  record('Top-1 仍为 APBT（预测本身不受开关影响）',
    (snap.topk[0]?.breed || '').includes('比特斗牛梗'), snap.topk[0]?.breed)

  await page.close()
  return { switchOff: snap }
}

async function main() {
  const scenario = process.argv.includes('--scenario')
    ? process.argv[process.argv.indexOf('--scenario') + 1]
    : 'on'

  mkdirSync(SHOTS, { recursive: true })

  const browser = await chromium.launch({
    channel: 'chrome',
    headless: true,
  })
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
  for (const item of failed) {
    console.log(`    FAIL: ${item.check} — ${item.detail}`)
  }

  const outPath = resolve(OUT, `page_acceptance_evidence_${scenario}.json`)
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
