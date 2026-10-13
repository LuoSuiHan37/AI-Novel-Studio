/** Soft AlphaNovel checklist for the chapter editor (mirrors platform preset). */

export const ALPHANOVEL_RULES = {
  wordMin: 1500,
  wordMax: 2500,
  requiredBeats: ["conflict", "emotional_beat", "plot_progress"] as const,
  ending: "hook_or_cliffhanger",
  monitoredPhrases: [
    "she froze",
    "his eyes darkened",
    "her heart skipped a beat",
    "you are mine",
    "a smirk played on his lips",
    "electricity shot through",
  ],
};

export type PlatformCheck = {
  id: string;
  label: string;
  ok: boolean;
  detail: string;
};

function wordCount(text: string): number {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  return trimmed.split(/\s+/).length;
}

export function evaluateAlphaNovelChecks(input: {
  prose: string;
  conflict?: string;
  emotionalArc?: string;
  cliffhanger?: string;
  chapterGoal?: string;
}): PlatformCheck[] {
  const words = wordCount(input.prose);
  const paragraphs = input.prose
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);
  const avgParagraphWords =
    paragraphs.length === 0
      ? 0
      : Math.round(paragraphs.reduce((sum, p) => sum + wordCount(p), 0) / paragraphs.length);

  const phraseHits = ALPHANOVEL_RULES.monitoredPhrases
    .map((phrase) => {
      const re = new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
      const count = (input.prose.match(re) || []).length;
      return { phrase, count };
    })
    .filter((item) => item.count > 0);

  const hasConflict = Boolean((input.conflict || "").trim()) || /\b(reject|fight|threat|betray)/i.test(input.prose);
  const hasEmotion =
    Boolean((input.emotionalArc || "").trim()) ||
    /\b(hurt|rage|desire|shame|bond|heart)\b/i.test(input.prose);
  const hasProgress = Boolean((input.chapterGoal || "").trim()) || words >= ALPHANOVEL_RULES.wordMin;
  const hasHook =
    Boolean((input.cliffhanger || "").trim()) ||
    /\?\s*$/.test(input.prose.trim()) ||
    /\b(suddenly|stranger|voice|door)\b/i.test(input.prose.slice(-400));

  return [
    {
      id: "words",
      label: "章长 1500–2500 词",
      ok: words >= ALPHANOVEL_RULES.wordMin && words <= ALPHANOVEL_RULES.wordMax,
      detail: words === 0 ? "尚无正文" : `当前约 ${words} 词`,
    },
    {
      id: "paragraphs",
      label: "短段落节奏",
      ok: paragraphs.length === 0 || avgParagraphWords <= 80,
      detail: paragraphs.length === 0 ? "尚无正文" : `平均每段约 ${avgParagraphWords} 词`,
    },
    {
      id: "conflict",
      label: "冲突节拍",
      ok: hasConflict,
      detail: hasConflict ? "计划或正文含冲突信号" : "补充冲突（计划或正文）",
    },
    {
      id: "emotion",
      label: "情绪节拍",
      ok: hasEmotion,
      detail: hasEmotion ? "计划或正文含情绪信号" : "补充 emotional beat",
    },
    {
      id: "progress",
      label: "情节推进",
      ok: hasProgress,
      detail: hasProgress ? "有章节目标 / 足够篇幅" : "补充 chapter goal",
    },
    {
      id: "hook",
      label: "章末钩子 / 悬念",
      ok: hasHook,
      detail: hasHook ? "计划 cliffhanger 或结尾含悬念" : "补 cliffhanger 或悬念结尾",
    },
    {
      id: "phrases",
      label: "高频套话监测",
      ok: phraseHits.length === 0,
      detail:
        phraseHits.length === 0
          ? "未命中监测短语"
          : phraseHits.map((item) => `${item.phrase}×${item.count}`).join(" · "),
    },
  ];
}
