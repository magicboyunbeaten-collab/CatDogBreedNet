/**
 * 136 类中文显示名（V2.1 / 136 类正式模型）。
 *
 * 键**完全等于** `artifacts/v2_1_136classes_seed42/class_names.json` 中的
 * canonical label，顺序与该文件一致（即模型输出顺序），大小写与下划线保持
 * 原样，不做任何合并或重命名。未知标签回退英文原名，因此缺映射不会渲染成空。
 *
 * 本文件仅用于显示：模型权重、后端 API、数据库与实验报告一律保留原始
 * 英文 canonical label。
 *
 * 名称来源：`reports/v2_class_catalog.csv` 的 `chinese_name`（已审核目录）。
 * 原有 37 类的中文名与 V1.1 时期**完全一致**，未做任何改写。
 * 由 `scripts/generate_breed_mapping.py` 生成，请勿手工编辑。
 */

const BREED_NAMES_ZH = {
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
  affenpinscher: '猴面梗',
  afghan_hound: '阿富汗猎犬',
  african_hunting_dog: '非洲野犬',
  airedale: '艾尔谷梗',
  american_bulldog: '美国斗牛犬',
  american_pit_bull_terrier: '美国比特斗牛梗',
  american_staffordshire_terrier: '美国斯塔福郡梗',
  appenzeller: '阿彭策尔山犬',
  australian_terrier: '澳大利亚梗',
  basenji: '巴辛吉犬',
  basset_hound: '巴吉度猎犬',
  beagle: '比格犬',
  bedlington_terrier: '贝灵顿梗',
  bernese_mountain_dog: '伯恩山犬',
  black_and_tan_coonhound: '黑褐猎浣熊犬',
  blenheim_spaniel: '布伦海姆西班牙猎犬',
  bloodhound: '寻血猎犬',
  bluetick: '蓝斑猎浣熊犬',
  border_collie: '边境牧羊犬',
  border_terrier: '边境梗',
  borzoi: '苏俄猎狼犬',
  boston_bull: '波士顿梗',
  bouvier_des_flandres: '佛兰德牧牛犬',
  boxer: '拳师犬',
  brabancon_griffon: '布拉班松格里芬犬',
  briard: '布里牧羊犬',
  brittany_spaniel: '布列塔尼西班牙猎犬',
  bull_mastiff: '斗牛獒犬',
  cairn: '凯恩梗',
  cardigan: '卡迪根威尔士柯基犬',
  chesapeake_bay_retriever: '切萨皮克湾寻回犬',
  chihuahua: '吉娃娃',
  chow: '松狮犬',
  clumber: '克伦伯西班牙猎犬',
  collie: '柯利牧羊犬',
  curly_coated_retriever: '卷毛寻回犬',
  dandie_dinmont: '丹迪丁蒙梗',
  dhole: '豺',
  dingo: '澳洲野犬',
  doberman: '杜宾犬',
  english_cocker_spaniel: '英国可卡犬',
  english_foxhound: '英国猎狐犬',
  english_setter: '英国塞特犬',
  english_springer: '英国跳猎犬',
  entlebucher: '恩特布赫山犬',
  eskimo_dog: '爱斯基摩犬',
  flat_coated_retriever: '平毛寻回犬',
  french_bulldog: '法国斗牛犬',
  german_shepherd: '德国牧羊犬',
  german_shorthaired: '德国短毛指示犬',
  giant_schnauzer: '巨型雪纳瑞',
  golden_retriever: '金毛寻回犬',
  gordon_setter: '戈登塞特犬',
  great_dane: '大丹犬',
  great_pyrenees: '大白熊犬',
  greater_swiss_mountain_dog: '大瑞士山地犬',
  groenendael: '格罗安达牧羊犬',
  havanese: '哈瓦那犬',
  ibizan_hound: '伊比赞猎犬',
  irish_setter: '爱尔兰塞特犬',
  irish_terrier: '爱尔兰梗',
  irish_water_spaniel: '爱尔兰水猎犬',
  irish_wolfhound: '爱尔兰猎狼犬',
  italian_greyhound: '意大利灵缇',
  japanese_chin: '日本狆',
  keeshond: '荷兰毛狮犬',
  kelpie: '凯尔皮牧羊犬',
  kerry_blue_terrier: '凯利蓝梗',
  komondor: '可蒙犬',
  kuvasz: '库瓦兹犬',
  labrador_retriever: '拉布拉多寻回犬',
  lakeland_terrier: '湖畔梗',
  leonberger: '莱昂贝格犬',
  lhasa: '拉萨犬',
  malamute: '阿拉斯加马拉缪特',
  malinois: '马里努阿犬',
  maltese_dog: '马尔济斯犬',
  mexican_hairless: '墨西哥无毛犬',
  miniature_pinscher: '迷你杜宾',
  miniature_poodle: '迷你贵宾犬',
  miniature_schnauzer: '迷你雪纳瑞',
  newfoundland: '纽芬兰犬',
  norfolk_terrier: '诺福克梗',
  norwegian_elkhound: '挪威猎麋犬',
  norwich_terrier: '诺里奇梗',
  old_english_sheepdog: '英国古代牧羊犬',
  otterhound: '水獭猎犬',
  papillon: '蝴蝶犬',
  pekinese: '京巴犬',
  pembroke: '彭布罗克威尔士柯基犬',
  pomeranian: '博美犬',
  pug: '巴哥犬',
  redbone: '红骨猎浣熊犬',
  rhodesian_ridgeback: '罗得西亚脊背犬',
  rottweiler: '罗威纳犬',
  saint_bernard: '圣伯纳犬',
  saluki: '萨卢基猎犬',
  samoyed: '萨摩耶犬',
  schipperke: '西帕基犬',
  scottish_deerhound: '苏格兰猎鹿犬',
  scottish_terrier: '苏格兰梗',
  sealyham_terrier: '西里汉梗',
  shetland_sheepdog: '喜乐蒂牧羊犬',
  shiba_inu: '柴犬',
  shih_tzu: '西施犬',
  siberian_husky: '西伯利亚哈士奇',
  silky_terrier: '丝毛梗',
  staffordshire_bull_terrier: '斯塔福郡斗牛梗',
  standard_poodle: '标准贵宾犬',
  standard_schnauzer: '标准雪纳瑞',
  sussex_spaniel: '苏塞克斯西班牙猎犬',
  tibetan_mastiff: '藏獒',
  tibetan_terrier: '西藏梗',
  toy_poodle: '玩具贵宾犬',
  toy_terrier: '玩具梗',
  vizsla: '维兹拉犬',
  walker_hound: '沃克猎狐犬',
  weimaraner: '魏玛犬',
  welsh_springer_spaniel: '威尔士跳猎犬',
  west_highland_white_terrier: '西高地白梗',
  wheaten_terrier: '软毛麦色梗',
  whippet: '惠比特犬',
  wire_haired_fox_terrier: '刚毛猎狐梗',
  yorkshire_terrier: '约克夏梗',
}

/**
 * 相近犬种候选组的附加中文名（V2.1 候选模型能力，U5.2 方案 B1 四类）。
 *
 * 与 BREED_NAMES_ZH 中的同名条目保持一致；单独保留一份，供候选面板在
 * 不依赖完整映射的情况下也能正确显示。
 */
export const CANDIDATE_BREED_NAMES_ZH = {
  american_pit_bull_terrier: '美国比特斗牛梗',
  american_staffordshire_terrier: '美国斯塔福郡梗',
  staffordshire_bull_terrier: '斯塔福郡斗牛梗',
  american_bulldog: '美国斗牛犬',
}

/** 候选组的 canonical label（与后端 CANDIDATE_GROUP 保持一致）。 */
export const CANDIDATE_GROUP = [
  'american_pit_bull_terrier',
  'american_staffordshire_terrier',
  'staffordshire_bull_terrier',
  'american_bulldog',
]

/** Chinese display name for a breed label; falls back to the raw label. */
export function getBreedDisplayName(breed) {
  if (!breed) return ''
  return BREED_NAMES_ZH[breed] || CANDIDATE_BREED_NAMES_ZH[breed] || breed
}

/** A copy of the full mapping (136 entries for the V2.1 class space). */
export function getBreedMapping() {
  return { ...BREED_NAMES_ZH }
}

export const BREED_MAPPING_SIZE = Object.keys(BREED_NAMES_ZH).length
