import type { Chapter, Character, MasterPlot, Project, StoryArc, StoryBible, WorldBible } from "@/lib/types";

export type ChecklistItem = {
  id: string;
  label: string;
  done: boolean;
  href: string;
  hint: string;
};

export type NextAction = {
  label: string;
  href: string;
  description: string;
  /** Primary CTA advances pipeline once, then navigates to href. */
  advanceFirst?: boolean;
};

function approved(status: string | undefined | null): boolean {
  return (status || "").toLowerCase() === "approved";
}

export function buildChecklist(
  projectId: string,
  data: {
    story: StoryBible | null;
    world: WorldBible | null;
    characters: Character[];
    plot: MasterPlot | null;
    arcs: StoryArc[];
    chapters: Chapter[];
  },
): ChecklistItem[] {
  const base = `/projects/${projectId}`;
  const hasApprovedArc = data.arcs.some((item) => approved(item.status));
  const hasChapter = data.chapters.length > 0;
  const hasDraftText = data.chapters.some((item) => (item.content || "").trim().length > 0);

  return [
    {
      id: "story",
      label: "故事圣经已就绪（自动确定）",
      done: approved(data.story?.status),
      href: `${base}/story`,
      hint: data.story ? `状态：${data.story.status}` : "尚未填写",
    },
    {
      id: "world",
      label: "世界观硬规则已就绪（自动确定）",
      done: approved(data.world?.status),
      href: `${base}/world`,
      hint: data.world ? `状态：${data.world.status}` : "尚未填写",
    },
    {
      id: "characters",
      label: "角色已就绪（自动确定）",
      done: data.characters.length > 0 && data.characters.every((item) => approved(item.status)),
      href: `${base}/characters`,
      hint: `${data.characters.length} 个角色`,
    },
    {
      id: "plot",
      label: "主线情节已就绪（自动确定）",
      done: approved(data.plot?.status),
      href: `${base}/plot`,
      hint: data.plot ? `状态：${data.plot.status}` : "尚未填写",
    },
    {
      id: "arcs",
      label: "故事弧已就绪（自动确定）",
      done: hasApprovedArc,
      href: `${base}/arcs`,
      hint: `${data.arcs.length} 个故事弧`,
    },
    {
      id: "chapter",
      label: "章节计划已就绪（自动确定） / 正文",
      done: hasChapter,
      href: `${base}/chapters`,
      hint: hasDraftText ? `${data.chapters.length} 章（含正文）` : `${data.chapters.length} 章`,
    },
  ];
}

export function resolveNextAction(
  project: Project,
  checklist: ChecklistItem[],
  chapters: Chapter[],
): NextAction {
  const base = `/projects/${project.id}`;
  const stage = (project.current_stage || "idea").toLowerCase();
  const incomplete = checklist.find((item) => !item.done);

  if (stage === "idea") {
    return {
      label: "开始策划",
      href: `${base}/story`,
      description: "点一次即可进入故事圣经；系统会先推进阶段门禁。",
      advanceFirst: true,
    };
  }

  if (incomplete?.id === "story") {
    return {
      label: "完善故事圣经",
      href: `${base}/story`,
      description: "填写前提 / 主题并保存，系统会自动确定。",
    };
  }
  if (incomplete?.id === "world") {
    return {
      label: "完善世界观",
      href: `${base}/world`,
      description: "写一条硬性规则并保存，系统会自动确定。",
    };
  }
  if (incomplete?.id === "characters") {
    return {
      label: "添加核心角色",
      href: `${base}/characters`,
      description: "添加女主后即可使用；建议再补恋爱对象。",
    };
  }
  if (incomplete?.id === "plot") {
    return {
      label: "完善主线情节",
      href: `${base}/plot`,
      description: "搭好商业节拍并保存，系统会自动确定。",
    };
  }
  if (incomplete?.id === "arcs") {
    return {
      label: "添加故事弧",
      href: `${base}/arcs`,
      description: "添加连载分段（如 Rejection Arc）并保存。",
    };
  }

  if (chapters.length === 0) {
    return {
      label: "打开章节工作台",
      href: `${base}/chapters`,
      description: "点「创建第 1 章并打开」，再到编辑器点「生成本章」出正文。",
    };
  }

  const latest = [...chapters].sort((a, b) => b.chapter_number - a.chapter_number)[0];
  const targetNo = latest?.content?.trim()
    ? latest.chapter_number
    : latest?.chapter_number || 1;

  return {
    label: `打开第 ${targetNo} 章工作台`,
    href: `${base}/chapters/${targetNo}`,
    description: "写作主界面：生成本章 → 改稿 → 保存 → 批准。",
  };
}
