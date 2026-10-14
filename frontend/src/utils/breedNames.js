/**
 * Chinese display names for the 37 Oxford-IIIT Pet breeds.
 *
 * The keys are EXACTLY the labels stored in artifacts/class_names.json
 * (model output order and case preserved). Unknown labels fall back to the
 * original English name, so a missing mapping can never render blank.
 * This file is display-only: model weights, the backend API, the database
 * and all experiment reports keep the original English labels.
 */

const BREED_NAMES_ZH = {
  // --- 12 cat breeds ---
  Abyssinian: '阿比西尼亚猫',
  Bengal: '孟加拉猫',
  Birman: '伯曼猫',
  Bombay: '孟买猫',
  British_Shorthair: '英国短毛猫',
  Egyptian_Mau: '埃及猫',
  Maine_Coon: '缅因猫',
  Persian: '波斯猫',
  Ragdoll: '布偶猫',
  Russian_Blue: '俄罗斯蓝猫',
  Siamese: '暹罗猫',
  Sphynx: '斯芬克斯猫',

  // --- 25 dog breeds ---
  american_bulldog: '美国斗牛犬',
  american_pit_bull_terrier: '美国比特斗牛梗',
  basset_hound: '巴吉度猎犬',
  beagle: '比格犬',
  boxer: '拳师犬',
  chihuahua: '吉娃娃',
  english_cocker_spaniel: '英国可卡犬',
  english_setter: '英国塞特犬',
  german_shorthaired: '德国短毛指示犬',
  great_pyrenees: '大白熊犬',
  havanese: '哈瓦那犬',
  japanese_chin: '日本狆',
  keeshond: '荷兰毛狮犬',
  leonberger: '莱昂贝格犬',
  miniature_pinscher: '迷你杜宾',
  newfoundland: '纽芬兰犬',
  pomeranian: '博美犬',
  pug: '巴哥犬',
  saint_bernard: '圣伯纳犬',
  samoyed: '萨摩耶犬',
  scottish_terrier: '苏格兰梗',
  shiba_inu: '柴犬',
  staffordshire_bull_terrier: '斯塔福郡斗牛梗',
  wheaten_terrier: '软毛麦色梗',
  yorkshire_terrier: '约克夏梗',
}

/** Chinese display name for a breed label; falls back to the raw label. */
export function getBreedDisplayName(breed) {
  if (!breed) return ''
  return BREED_NAMES_ZH[breed] || breed
}

/** A copy of the full mapping (37 entries). */
export function getBreedMapping() {
  return { ...BREED_NAMES_ZH }
}

export const BREED_MAPPING_SIZE = Object.keys(BREED_NAMES_ZH).length
