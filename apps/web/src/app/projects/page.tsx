"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { getGenreCategory, genreOptionLabel, NOVEL_GENRES, type GenreCategory } from "@/lib/genres";
import { genreLabel, pipelineStageLabel } from "@/lib/labels";
import type { Project, ResearchSession } from "@/lib/types";

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [genre, setGenre] = useState("werewolf_romance");
  const [genreCategory, setGenreCategory] = useState<GenreCategory>(() => getGenreCategory("werewolf_romance"));
  const [language, setLanguage] = useState("zh-CN");
  const [chapterCountTarget, setChapterCountTarget] = useState("120");
  const [title, setTitle] = useState("");
  const [brief, setBrief] = useState("");
  const [pitch, setPitch] = useState<{
    premise: string;
    theme: string;
    logline: string;
    synopsis: string;
    reading_tags: string[];
    content_tags: string[];
    protagonist_names: string[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [titleAvailable, setTitleAvailable] = useState(false);
  const [distillUrl, setDistillUrl] = useState("");
  const [distillProjectId, setDistillProjectId] = useState<string | null>(null);
  const [distillSession, setDistillSession] = useState<ResearchSession | null>(null);
  const [distilling, setDistilling] = useState(false);
  const distillationCompleted = Boolean(
    distillSession?.status === "completed" &&
      distillSession.active_task?.status !== "error" &&
      distillSession.stages.length > 0 &&
      distillSession.stages.every((stage) => stage.status === "done"),
  );
  const distillationFailed = distillSession?.status === "failed" || distillSession?.active_task?.status === "error";

  function resetGeneratedPackage() {
    setTitle("");
    setPitch(null);
    setTitleAvailable(false);
  }

  function selectGenre(value: string) {
    setGenre(value);
    setTitle("");
    setPitch(null);
    setTitleAvailable(false);
  }

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setProjects(await api<Project[]>("/projects"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function createProject() {
    if (!distillProjectId || !distillationCompleted) {
      setError("请先完成参考小说蒸馏");
      return;
    }
    if (!title.trim() || !pitch) {
      setError("请先生成书名和小说介绍");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await api(`/projects/${distillProjectId}/research/inject/approve`, {
        method: "POST",
        projectId: distillProjectId,
        body: JSON.stringify({ confirmed_by: "studio-user", note: "Approved while creating the novel" }),
      });
      const created = await api<Project>(`/projects/${distillProjectId}`, {
        method: "PATCH",
        projectId: distillProjectId,
        body: JSON.stringify({
          title,
          genre,
          language,
          chapter_count_target: Number(chapterCountTarget),
          tone: genre.replaceAll("_", " "),
        }),
      });
      await api(`/projects/${created.id}/story`, {
        method: "PATCH",
        projectId: created.id,
        body: JSON.stringify({
          premise: pitch.premise,
          theme: pitch.theme,
          tone: genre.replaceAll("_", " "),
          narrative_style: "close third serial",
          target_word_count: 80000,
          chapter_word_count: language === "zh-CN" ? 2500 : 1800,
          romance_level: "high",
          violence_level: "medium",
          heat_level: "medium",
          tropes: [genre],
          logline: pitch.logline,
          synopsis: pitch.synopsis,
          target_reader: genreCategory === "female" ? "female" : "male",
          reading_tags: pitch.reading_tags,
          content_tags: pitch.content_tags,
          protagonist_names: pitch.protagonist_names,
        }),
      });
      setOk("项目已创建");
      router.push(`/projects/${created.id}/story`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "创建失败");
    } finally {
      setSaving(false);
    }
  }

  async function suggestTitle() {
    if (!distillSession || !distillationCompleted) {
      setError("请先完成参考小说蒸馏，再生成书名和简介");
      return;
    }
    setSuggesting(true);
    setError(null);
    try {
      const result = await api<{
        title: string;
        available: boolean;
        premise: string;
        theme: string;
        logline: string;
        synopsis: string;
        reading_tags: string[];
        content_tags: string[];
        protagonist_names: string[];
      }>("/projects/title-suggestion", {
        method: "POST",
        body: JSON.stringify({
          genre,
          target_platform: "alphanovel",
          language,
          brief,
          research_profile: distillSession.artifacts.find((item) => item.id === "profile")?.content || null,
        }),
      });
      setTitle(result.title);
      setPitch({
        premise: result.premise,
        theme: result.theme,
        logline: result.logline,
        synopsis: result.synopsis,
        reading_tags: result.reading_tags || [],
        content_tags: result.content_tags || [],
        protagonist_names: result.protagonist_names || [],
      });
      setTitleAvailable(result.available);
      if (!result.available) setError(`AI 生成的书名“${result.title}”已存在，请重新生成。`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "AI 书名和小说介绍生成失败");
    } finally {
      setSuggesting(false);
    }
  }

  async function executeDistillationStage(projectId: string, stageId: string) {
    let polling = true;
    const poll = async () => {
      if (!polling) return;
      try {
        const live = await api<ResearchSession>(`/projects/${projectId}/research`);
        setDistillSession(live);
      } catch {
        // The stage request remains the source of truth; transient polling
        // failures must not turn a successful stage into a false failure.
      }
    };
    const timer = window.setInterval(() => void poll(), 800);
    try {
      return await api<ResearchSession>(`/projects/${projectId}/research/stages/${stageId}`, {
        method: "POST",
        projectId,
        body: JSON.stringify({ status: "done", execute: true }),
      });
    } finally {
      polling = false;
      window.clearInterval(timer);
    }
  }

  async function startDistillation() {
    if (!distillUrl.trim()) {
      setError("请先输入番茄小说链接");
      return;
    }
    setDistilling(true);
    setError(null);
    try {
      const project = await api<Project>("/projects", {
        method: "POST",
        body: JSON.stringify({
          // Distillation starts from a temporary project. It must be unique so
          // a failed or retried run cannot collide with an older draft.
          title: `待生成书名-${genreOptionLabel(genre)}-${Date.now().toString(36)}`,
          genre,
          tropes: [genre],
          target_platform: "alphanovel",
          language,
        }),
      });
      setDistillProjectId(project.id);
      let session = await api<ResearchSession>(`/projects/${project.id}/research/sources`, {
        method: "POST",
        projectId: project.id,
        body: JSON.stringify({ title: "番茄参考小说", source_type: "fanqie_url", url: distillUrl.trim() }),
      });
      session = await api<ResearchSession>(`/projects/${project.id}/research/start`, { method: "POST", projectId: project.id });
      setDistillSession(session);
      while (true) {
        const stage = session.stages.find((item) => item.status === "running");
        if (!stage) break;
        session = await executeDistillationStage(project.id, stage.id);
        setDistillSession(session);
        if (session.status === "failed" || session.active_task?.status === "error") {
          throw new Error(session.active_task?.message || `蒸馏阶段“${stage.title}”失败`);
        }
      }
      if (session.status !== "completed" || !session.stages.every((stage) => stage.status === "done")) {
        throw new Error("蒸馏尚未完成");
      }
      if (session.stages.some((stage) => stage.id === "inject" && stage.status === "running")) {
        session = await executeDistillationStage(project.id, "inject");
      }
      setDistillSession(session);
      setOk("参考小说蒸馏和原创创作包已完成，确认创建新书后会写入角色、世界观和分卷");
    } catch (err) {
      setError(err instanceof Error ? err.message : "蒸馏执行失败");
    } finally {
      setDistilling(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">我的书籍</h1>
          <p className="text-sm text-muted-foreground">每本书拥有独立的设定、目录、章节、故事记忆和爆款研究。</p>
        </div>
        {projects.length ? (
          <Link href="/research" className={buttonVariants({ variant: "outline", size: "sm" })}>
            蒸馏参考小说
          </Link>
        ) : null}
      </div>
      <StatusBanner loading={loading} error={error} ok={ok} />
      <div className="max-w-xl space-y-2 rounded-lg border bg-muted/20 p-4">
        <h2 className="font-medium">创建新书</h2>
        <div className="space-y-2 rounded-md border border-dashed bg-background p-3">
          <div>
            <p className="text-sm font-medium">第一步：蒸馏番茄参考小说</p>
            <p className="mt-1 text-xs text-muted-foreground">先选择题材并输入番茄小说链接，提取结构、节奏、文案和表达规律。</p>
          </div>
          <div className="flex gap-2">
            <input
              className="min-w-0 flex-1 rounded-md border bg-background px-3 py-2 text-sm"
              placeholder="粘贴番茄小说链接"
              value={distillUrl}
              disabled={distilling || Boolean(distillSession)}
              onChange={(event) => setDistillUrl(event.target.value)}
            />
            <Button variant="outline" disabled={distilling || distillationCompleted} onClick={() => void startDistillation()}>
              {distilling ? "蒸馏执行中…" : distillationCompleted ? "已完成蒸馏" : "开始蒸馏"}
            </Button>
          </div>
          {distillSession ? (
            <div className="space-y-1 rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
              <p>
                蒸馏进度：{distillationCompleted ? "100%" : `${distillSession.progress}%`} · {distillationCompleted ? "已完成" : distillationFailed ? "失败" : "正在执行"}
              </p>
              {distillationFailed ? (
                <p className="text-destructive">失败：{distillSession.active_task?.message || "未知错误"}</p>
              ) : distillSession.active_task?.source_title ? (
                <p>
                  当前小说：{distillSession.active_task.source_title}
                  {distillSession.active_task.sampled_chapter_numbers?.length ? (
                    <> · 当前采样章节：第 {distillSession.active_task.sampled_chapter_numbers.join("、")} 章</>
                  ) : null}
                  {distillSession.active_task.status === "completed" ? " · 本次分析已成功返回" : " · 正在分析"}
                </p>
              ) : null}
            </div>
          ) : null}
        </div>
          <Field
            label="核心创意（选填；填写后简介会更贴合你的故事）"
          value={brief}
          onChange={(value) => {
            setBrief(value);
            resetGeneratedPackage();
          }}
          multiline
          rows={3}
          />
        <label className="block space-y-1">
          <span className="text-xs font-medium text-muted-foreground">计划总章节数</span>
          <input
            className="w-40 rounded-md border border-input bg-background px-3 py-2 text-sm"
            type="number"
            min={1}
            max={5000}
            value={chapterCountTarget}
            onChange={(event) => setChapterCountTarget(event.target.value)}
          />
          <span className="ml-2 text-xs text-muted-foreground">创建后将作为生成和发布的硬约束</span>
        </label>
        <div className="flex flex-wrap items-end gap-2">
          <label className="block min-w-40 space-y-1">
            <span className="text-xs font-medium text-muted-foreground">小说语言</span>
            <select
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={language}
              onChange={(event) => {
                setLanguage(event.target.value);
                resetGeneratedPackage();
              }}
            >
              <option value="zh-CN">简体中文</option>
              <option value="en">English</option>
            </select>
          </label>
          <div className="min-w-60 flex-1 space-y-2">
            <span className="text-xs font-medium text-muted-foreground">小说类型</span>
            <div className="flex gap-2" role="tablist" aria-label="小说类型大类">
              {(["male", "female"] as GenreCategory[]).map((category) => (
                <button
                  key={category}
                  type="button"
                  role="tab"
                  aria-selected={genreCategory === category}
                  className={`rounded-full px-4 py-1.5 text-sm transition ${
                    genreCategory === category ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/70"
                  }`}
                  onClick={() => {
                    setGenreCategory(category);
                    selectGenre(NOVEL_GENRES[category][0].value);
                  }}
                >
                  {category === "male" ? "男频" : "女频"}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2" role="listbox" aria-label={`${genreCategory === "male" ? "男频" : "女频"}题材`}>
              {NOVEL_GENRES[genreCategory].map((option) => (
                <button
                  key={option.value}
                  type="button"
                  role="option"
                  aria-selected={genre === option.value}
                  className={`rounded-full border px-3 py-1.5 text-xs transition ${
                    genre === option.value
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-background text-muted-foreground hover:border-primary/60 hover:text-foreground"
                  }`}
                  onClick={() => selectGenre(option.value)}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">当前选择：{genreOptionLabel(genre)}</p>
          </div>
          <Button variant="outline" disabled={suggesting || !distillationCompleted} onClick={() => void suggestTitle()}>
            {suggesting ? "生成中…" : pitch ? "重新生成书名和简介" : "第二步：生成书名和简介"}
          </Button>
        </div>
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <div className="flex-1">
            <Field label="AI 生成的书名" value={title} onChange={() => undefined} readOnly />
          </div>
          <Button disabled={saving || !title.trim() || !pitch || !distillProjectId} onClick={() => void createProject()}>
            {saving ? "创建中…" : "确认创作包并创建新书"}
          </Button>
        </div>
        {title && !titleAvailable ? (
          <p className="text-xs text-amber-600">书名可能与已有书籍重复；如确认继续创建，请直接点击上方按钮。</p>
        ) : null}
        {pitch ? (
          <div className="space-y-2 border-t pt-3">
            <p className="text-sm font-medium">AI 生成的小说介绍（创建后仍可修改）</p>
            <Field label="Premise（故事前提）" value={pitch.premise} onChange={(premise) => setPitch({ ...pitch, premise })} multiline rows={3} />
            <Field label="Theme（主题）" value={pitch.theme} onChange={(theme) => setPitch({ ...pitch, theme })} />
            <Field label="Logline（一句话钩子）" value={pitch.logline} onChange={(logline) => setPitch({ ...pitch, logline })} />
            <Field label="Synopsis（读者向简介）" value={pitch.synopsis} onChange={(synopsis) => setPitch({ ...pitch, synopsis })} multiline rows={5} />
            <Field label="自动填充的阅读标签" value={pitch.reading_tags.join(", ")} onChange={(value) => setPitch({ ...pitch, reading_tags: value.split(",").map((item) => item.trim()).filter(Boolean) })} />
            <Field label="自动填充的内容标签" value={pitch.content_tags.join(", ")} onChange={(value) => setPitch({ ...pitch, content_tags: value.split(",").map((item) => item.trim()).filter(Boolean) })} />
            <Field label="自动填充的主角名" value={pitch.protagonist_names.join(", ")} onChange={(value) => setPitch({ ...pitch, protagonist_names: value.split(",").map((item) => item.trim()).filter(Boolean) })} />
          </div>
        ) : null}
      </div>
      <ul className="divide-y rounded-lg border">
        {projects.map((project) => (
          <li key={project.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <div className="font-medium">{project.title}</div>
              <div className="text-xs text-muted-foreground">
                {genreLabel(project.genre)} · {pipelineStageLabel(project.current_stage)}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Link className="text-sm underline" href={`/projects/${project.id}/chapters`}>
                打开目录
              </Link>
              <Link className={buttonVariants({ variant: "ghost", size: "sm" })} href={`/projects/${project.id}/story`}>
                小说介绍
              </Link>
              <Link className={buttonVariants({ variant: "outline", size: "sm" })} href={`/projects/${project.id}/research`}>
                爆款研究
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
