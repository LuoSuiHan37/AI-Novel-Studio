export type GenreCategory = "male" | "female";

export type NovelGenre = {
  value: string;
  label: string;
};

export const NOVEL_GENRES: Record<GenreCategory, NovelGenre[]> = {
  male: [
    { value: "western_fantasy", label: "西方奇幻" },
    { value: "eastern_xianxia", label: "东方仙侠" },
    { value: "sci_fi_apocalypse", label: "科幻末世" },
    { value: "urban_daily", label: "都市日常" },
    { value: "urban_cultivation", label: "都市修真" },
    { value: "urban_martial", label: "都市高武" },
    { value: "historical_ancient", label: "历史古代" },
    { value: "war_god_live_in", label: "战神赘婿" },
    { value: "urban_farming", label: "都市种田" },
    { value: "traditional_fantasy", label: "传统玄幻" },
    { value: "historical_what_if", label: "历史脑洞" },
    { value: "mystery_what_if", label: "悬疑脑洞" },
    { value: "urban_what_if", label: "都市脑洞" },
    { value: "fantasy_what_if", label: "玄幻脑洞" },
    { value: "mystery_supernatural", label: "悬疑灵异" },
    { value: "war_spy", label: "抗战谍战" },
    { value: "game_sports", label: "游戏体育" },
    { value: "anime_fanfic", label: "动漫衍生" },
    { value: "male_fanfic", label: "男频衍生" },
  ],
  female: [
    { value: "ancient_lifestyle", label: "古风世情" },
    { value: "sci_fi_apocalypse", label: "科幻末世" },
    { value: "game_sports", label: "游戏体育" },
    { value: "female_fanfic", label: "女频衍生" },
    { value: "fantasy_romance", label: "玄幻言情" },
    { value: "farming", label: "种田" },
    { value: "period_era", label: "年代" },
    { value: "contemporary_what_if", label: "现言脑洞" },
    { value: "palace_house", label: "宫斗宅斗" },
    { value: "mystery_what_if", label: "悬疑脑洞" },
    { value: "ancient_romance_what_if", label: "古言脑洞" },
    { value: "quick_transmigration", label: "快穿" },
    { value: "youth_sweet", label: "青春甜宠" },
    { value: "showbiz_romance", label: "星光璀璨" },
    { value: "female_mystery", label: "女频悬疑" },
    { value: "workplace_romance", label: "职场婚恋" },
    { value: "billionaire_romance", label: "豪门总裁" },
    { value: "republican_romance", label: "民国言情" },
    { value: "werewolf_romance", label: "狼人罗曼史" },
    { value: "contemporary_romance", label: "现代言情" },
    { value: "mystery", label: "悬疑推理" },
    { value: "science_fiction", label: "科幻" },
  ],
};

export function getGenreCategory(value: string): GenreCategory {
  return NOVEL_GENRES.male.some((genre) => genre.value === value) ? "male" : "female";
}

export function genreOptionLabel(value: string): string {
  for (const genres of Object.values(NOVEL_GENRES)) {
    const match = genres.find((genre) => genre.value === value);
    if (match) return match.label;
  }
  return value;
}
