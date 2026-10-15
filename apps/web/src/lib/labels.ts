/** UI labels for API enum / slug values. Unknown keys fall back to the raw value. */

const PROJECT_STATUS: Record<string, string> = {
  draft: "草稿",
  planning: "策划中",
  writing: "写作中",
  revising: "修订中",
  completed: "已完成",
  archived: "已归档",
};

const PLATFORM: Record<string, string> = {
  fanqie: "番茄",
  qidian: "起点",
  qimao: "七猫",
  zongheng: "纵横",
  shuqi: "书旗",
  alphanovel: "AlphaNovel",
  wattpad: "Wattpad",
  goodnovel: "GoodNovel",
};

const PIPELINE_STAGE: Record<string, string> = {
  idea: "创意",
  story_bible: "故事圣经",
  world_bible: "世界观",
  characters: "角色",
  master_plot: "主线情节",
  chapter_plan: "章节计划",
  drafting: "正文起草",
  review: "审阅",
  publish: "发布",
};

const CHAPTER_STATUS: Record<string, string> = {
  draft: "草稿",
  reviewed: "已审阅",
  approved: "已批准",
  published: "已发布",
};

const APPROVAL_STATUS: Record<string, string> = {
  draft: "草稿",
  pending_review: "待审阅",
  approved: "已批准",
  rejected: "已驳回",
};

const CHARACTER_ROLE: Record<string, string> = {
  protagonist: "主角",
  love_interest: "恋爱对象",
  antagonist: "反派",
  supporting: "配角",
  extra: "龙套",
};

const MEMORY_LAYER: Record<string, string> = {
  global: "全局",
  character: "角色",
  timeline: "时间线",
  chapter: "章节",
  vector: "向量",
};

const EPISTEMIC_STATUS: Record<string, string> = {
  confirmed_fact: "已确认事实",
  tentative_fact: "暂定事实",
  character_belief: "角色信念",
  rumor: "传闻",
  secret: "秘密",
};

const IMPORTANCE: Record<string, string> = {
  low: "低",
  medium: "中",
  high: "高",
  critical: "关键",
};

const HOOK_TYPE: Record<string, string> = {
  cliffhanger: "悬念结尾",
  question: "疑问",
  secret: "秘密",
  romance: "浪漫",
  danger: "危险",
  revelation: "揭示",
  delayed_payoff: "延迟兑现",
};

const HOOK_STATUS: Record<string, string> = {
  planned: "已计划",
  planted: "已埋设",
  active: "进行中",
  resolved: "已解决",
  dropped: "已放弃",
};

const FORESHADOW_STATUS: Record<string, string> = {
  planned: "已计划",
  planted: "已埋设",
  paid_off: "已兑现",
  missed: "已错过",
  dropped: "已放弃",
};

const GENRE: Record<string, string> = {
  western_fantasy: "西方奇幻",
  eastern_xianxia: "东方仙侠",
  sci_fi_apocalypse: "科幻末世",
  urban_daily: "都市日常",
  urban_cultivation: "都市修真",
  urban_martial: "都市高武",
  historical_ancient: "历史古代",
  war_god_live_in: "战神赘婿",
  urban_farming: "都市种田",
  traditional_fantasy: "传统玄幻",
  historical_what_if: "历史脑洞",
  mystery_what_if: "悬疑脑洞",
  urban_what_if: "都市脑洞",
  fantasy_what_if: "玄幻脑洞",
  mystery_supernatural: "悬疑灵异",
  war_spy: "抗战谍战",
  game_sports: "游戏体育",
  anime_fanfic: "动漫衍生",
  male_fanfic: "男频衍生",
  ancient_lifestyle: "古风世情",
  female_fanfic: "女频衍生",
  fantasy_romance: "玄幻言情",
  farming: "种田",
  period_era: "年代",
  contemporary_what_if: "现言脑洞",
  palace_house: "宫斗宅斗",
  ancient_romance_what_if: "古言脑洞",
  quick_transmigration: "快穿",
  youth_sweet: "青春甜宠",
  showbiz_romance: "星光璀璨",
  female_mystery: "女频悬疑",
  workplace_romance: "职场婚恋",
  republican_romance: "民国言情",
  contemporary_romance: "现代言情",
  mystery: "悬疑推理",
  science_fiction: "科幻",
  werewolf_romance: "狼人罗曼史",
  billionaire_romance: "亿万富翁罗曼史",
};

function label(map: Record<string, string>, value: string | null | undefined): string {
  if (!value) return "";
  return map[value] || map[value.toLowerCase()] || value;
}

export function projectStatusLabel(value: string): string {
  return label(PROJECT_STATUS, value);
}

export function platformLabel(value: string | null | undefined): string {
  return label(PLATFORM, value);
}

export function pipelineStageLabel(value: string): string {
  return label(PIPELINE_STAGE, value);
}

export function chapterStatusLabel(value: string): string {
  return label(CHAPTER_STATUS, value);
}

export function approvalStatusLabel(value: string): string {
  return label(APPROVAL_STATUS, value);
}

export function characterRoleLabel(value: string): string {
  return label(CHARACTER_ROLE, value);
}

export function memoryLayerLabel(value: string): string {
  return label(MEMORY_LAYER, value);
}

export function epistemicStatusLabel(value: string): string {
  return label(EPISTEMIC_STATUS, value);
}

export function importanceLabel(value: string): string {
  return label(IMPORTANCE, value);
}

export function hookTypeLabel(value: string): string {
  return label(HOOK_TYPE, value);
}

export function hookStatusLabel(value: string): string {
  return label(HOOK_STATUS, value);
}

export function foreshadowStatusLabel(value: string): string {
  return label(FORESHADOW_STATUS, value);
}

export function genreLabel(value: string): string {
  return label(GENRE, value);
}

export function projectMetaLine(project: { status: string; current_stage: string }): string {
  return `${projectStatusLabel(project.status)} · ${pipelineStageLabel(project.current_stage)}`;
}
