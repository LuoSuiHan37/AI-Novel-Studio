import type { Project } from "@/lib/types";

export function displayProjectTitle(project?: Pick<Project, "title"> | null): string {
  const title = project?.title?.trim();
  if (!title || /^待生成书名-/.test(title) || /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(title)) return "未命名作品";
  return title;
}

export function projectCoverUrl(project?: Pick<Project, "extra_metadata"> | null): string | null {
  const value = project?.extra_metadata?.cover_url;
  return typeof value === "string" && value.trim() ? value : null;
}

export function formatProjectDate(value?: string): string {
  if (!value) return "更新时间未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "更新时间未知";
  return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}
