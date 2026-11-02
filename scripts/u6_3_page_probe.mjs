/**
 * U6.3 阶段 A3：候选区 UI 语义核验（Playwright + 系统 Chrome，隔离实例）。
 *
 * 用法（在仓库根目录执行）::
 *
 *   node scripts/u6_3_page_probe.mjs
 *
 * 核验语义（任务 §1-A3）：
 * 1. 原始 Top-1 / Top-K 与分数不被候选提示替换；
 * 2. 图例标注"候选组内相对得分"、版本号、"不是整体识别置信度"、
 *    "不保证候选中一定包含正确品种"；
 * 3. collie-pair 仅在阈值满足时出现（不按黑白毛色触发）；
 * 4. 用户选择仅独立显示，模型预测区文字不变；
 * 5. 不触发图片不渲染候选区。
 *
 * 截图写入 reports/u6_3_default_runtime_and_freeze/screenshots/。
 */
import { mkdirSync, writeFileSync, readdirSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
const { chromium } = require(process.env.PW_PATH || 'playwright')

const here = dirname(fileURLToPath(import.meta.url))
const REPO = resolve(here, '..')
const OUT = resolve(REPO, 'reports/u6_3_default_runtime_and_freeze')
const SHOTS = resolve(OUT, 'screenshots')
const BASE_URL = 'http://127.0.0.1:5173/predict'
const VAL = resolve(REPO, 'data/v2_processed/val')

const SAMPLES = {
  // collie-pair 已知触发图（真实标签 border_collie）
  pairTrigger: resolve(VAL, 'border_collie/n02106166_549.jpg'),
  // collie-pair 已知不触发图（Top-1=collie 但 margin 0.6297 > 0.30）
  pairNonTrigger: resolve(VAL, 'afghan_hound/n02088094_1479.jpg'),
  // 四类 bully 已知触发图
  bullyTrigger: resolve(VAL, 'american_pit_bull_terrier/american_pit_bull_terrier_132.jpg'),
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
  .map((c) => parseScore(c.scoreText)).reduce((a, b) => a + b, 0)

async function main() {
  mkdirSync(SHOTS, { recursive: true })
  const browser = await chromium.launch({ channel: 'chrome', headless: true })
  console.log('[u6.3] Chrome launched')
  const evidence = {}

  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })

    // ---- 场景 1：collie-pair 触发图 ----
    console.log('\n=== 场景 1：collie-pair 已知触发图 ===')
    await waitReady(page)
    await uploadAndPredict(page, SAMPLES.pairTrigger)
    const snap1 = await readResult(page)
    evidence.pairTrigger = snap1
    await page.screenshot({ path: resolve(SHOTS, '01_pair_trigger.png'), fullPage: true })

    record('1: 双候选区出现', snap1.hasCandidateBlock)
    record('1: 组标识为 collie-pair', snap1.groupId === 'collie-pair', snap1.groupId)
    record('1: 候选行为 2', snap1.candidates.length === 2, `实际 ${snap1.candidates.length}`)
    const names = snap1.candidates.map((c) => c.name).sort()
    record('1: 中文名为柯利牧羊犬/边境牧羊犬',
      JSON.stringify(names) === JSON.stringify(['柯利牧羊犬', '边境牧羊犬']),
      JSON.stringify(names))
    record('1: 组内得分和约 100%', Math.abs(sumScores(snap1) - 100) <= 0.05,
      `sum=${sumScores(snap1).toFixed(4)}`)
    record('1: 副标题如实说明是这两个牧羊犬难以区分',
      (snap1.subtitle || '').includes('柯利牧羊犬')
      && (snap1.subtitle || '').includes('边境牧羊犬'), snap1.subtitle)
    record('1: 图例含"候选组内相对得分"',
      (snap1.bodyText || '').includes('候选组内相对得分'))
    record('1: 图例含版本 val-2026-10-21-collie-pair-v1',
      (snap1.bodyText || '').includes('val-2026-10-21-collie-pair-v1'))
    record('1: 图例声明"不是整体识别置信度"',
      (snap1.bodyText || '').includes('不是整体识别置信度'))
    record('1: 文案声明"不保证候选中一定包含正确品种"',
      (snap1.bodyText || '').includes('不保证候选中一定包含正确品种'))
    record('1: 原始 Top-K 仍为 3 行', snap1.topk.length === 3, `实际 ${snap1.topk.length}`)
    const top1Before = snap1.topk[0]

    // ---- 场景 2：用户选择独立显示，模型预测区不变 ----
    console.log('\n=== 场景 2：用户选择后模型预测区不变 ===')
    await page.locator('.candidate-block .el-radio').nth(1).click()
    await page.waitForTimeout(400)
    const snap2 = await readResult(page)
    evidence.userSelection = snap2
    await page.screenshot({ path: resolve(SHOTS, '02_user_selection.png'), fullPage: true })

    record('2: "你选择的品种"出现', Boolean(snap2.userChoice))
    record('2: 选择值等于第 2 个候选',
      snap2.userChoice?.value === snap2.candidates[1]?.name,
      `${snap2.userChoice?.value} vs ${snap2.candidates[1]?.name}`)
    record('2: 提示"未被替换"', (snap2.userChoice?.hint || '').includes('未被替换'))
    record('2: 用户选择后原始 Top-1 标签不变',
      snap2.topk[0]?.breed === top1Before?.breed, snap2.topk[0]?.breed)
    record('2: 用户选择后原始 Top-1 分数文本不变',
      snap2.topk[0]?.scoreText === top1Before?.scoreText,
      `${top1Before?.scoreText} -> ${snap2.topk[0]?.scoreText}`)
    record('2: 用户选择后 Top-K 全部不变',
      JSON.stringify(snap2.topk) === JSON.stringify(snap1.topk))

    // ---- 场景 3：collie-pair 不触发图 ----
    console.log('\n=== 场景 3：collie-pair 已知不触发图 ===')
    await uploadAndPredict(page, SAMPLES.pairNonTrigger)
    const snap3 = await readResult(page)
    evidence.pairNonTrigger = snap3
    await page.screenshot({ path: resolve(SHOTS, '03_pair_non_trigger.png'), fullPage: true })

    record('3: 候选区完全不出现', snap3.hasCandidateBlock === false)
    record('3: "你选择的品种"不出现', snap3.userChoice === null)
    record('3: 原始 Top-K 仍为 3 行', snap3.topk.length === 3)
    record('3: 原始 Top-1 为"柯利牧羊犬"',
      (snap3.topk[0]?.breed || '') === '柯利牧羊犬', snap3.topk[0]?.breed)
    record('3: 未按毛色直接触发（不触发图同为黑白牧羊犬类图片）',
      snap3.hasCandidateBlock === false)

    // ---- 场景 4：四类 bully 触发图 ----
    console.log('\n=== 场景 4：四类 bully 已知触发图 ===')
    await uploadAndPredict(page, SAMPLES.bullyTrigger)
    const snap4 = await readResult(page)
    evidence.bullyTrigger = snap4
    await page.screenshot({ path: resolve(SHOTS, '04_bully_trigger.png'), fullPage: true })

    record('4: 四类候选区出现', snap4.hasCandidateBlock)
    record('4: 组标识为 four-breed-bully',
      snap4.groupId === 'four-breed-bully', snap4.groupId)
    record('4: 候选行为 4', snap4.candidates.length === 4, `实际 ${snap4.candidates.length}`)
    record('4: 组内得分和约 100%', Math.abs(sumScores(snap4) - 100) <= 0.05,
      `sum=${sumScores(snap4).toFixed(4)}`)
    record('4: 图例含版本 val-2026-10-19-four-breed-b1',
      (snap4.bodyText || '').includes('val-2026-10-19-four-breed-b1'))
    record('4: 两类策略版本未混用',
      !(snap4.bodyText || '').includes('val-2026-10-21-collie-pair-v1'))

    await page.close()
  } finally {
    await browser.close()
  }

  const passed = checks.filter((c) => c.passed).length
  const failed = checks.filter((c) => !c.passed)
  console.log(`\n[u6.3] ${passed}/${checks.length} 项通过，失败 ${failed.length} 项`)
  for (const item of failed) console.log(`    FAIL: ${item.check} — ${item.detail}`)

  writeFileSync(resolve(OUT, 'page_probe.json'), JSON.stringify({
    generatedAt: new Date().toISOString(),
    baseUrl: BASE_URL,
    samples: SAMPLES,
    checks,
    passed,
    total: checks.length,
    evidence,
  }, null, 2), 'utf-8')
  console.log(`[u6.3] wrote ${resolve(OUT, 'page_probe.json')}`)

  process.exit(failed.length === 0 ? 0 : 2)
}

main().catch((error) => {
  console.error('[u6.3] fatal:', error)
  process.exit(1)
})
