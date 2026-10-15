"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";

import { StatusBanner } from "@/components/ui-bits";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api, ApiError } from "@/lib/api";
import type { ResearchSession, ResearchStage, ResearchSource } from "@/lib/types";

type StageStatus = "done" | "running" | "pending";
const initialStages: ResearchStage[] = [
  {
    id: "ingest",
    title: "导入与切分",
    detail: "识别文件、章节边界、标题和文本质量",
    status: "pending",
    output: "等待读取真实研究状态",
  },
  {
    id: "analyze",
    title: "单本拆解",
    detail: "逐本提取人物、冲突、节拍、视角和叙事手法",
    status: "pending",
    output: "等待读取真实研究状态",
  },
  {
    id: "scan",
    title: "题材与市场扫描",
    detail: "对比开篇、钩子、节奏、卖点和读者承诺",
    status: "pending",
    output: "等待读取真实研究状态",
  },
  {
    id: "synthesis",
    title: "多本归纳",
    detail: "把具体文本提升为可迁移的创作规律",
    status: "pending",
    output: "等待上一步完成",
  },
  {
    id: "profile",
    title: "生成创作 Profile",
    detail: "形成结构、文案、节奏和表达控制项",
    status: "pending",
    output: "尚未生成",
  },
];

const dimensions = [
  { id: "overview", label: "总览", value: "爆款共性" },
  { id: "plot", label: "结构", value: "冲突升级" },
  { id: "pacing", label: "节奏", value: "钩子密度" },
  { id: "blurb", label: "文案", value: "读者承诺" },
  { id: "style", label: "表达", value: "可操作特征" },
];

function StatusDot({ status }: { status: StageStatus }) {
  return (
    <span
      className={cn(
        "mt-1 h-2.5 w-2.5 shrink-0 rounded-full",
        status === "done" && "bg-foreground",
        status === "running" && "bg-primary ring-4 ring-primary/15",
        status === "pending" && "border border-muted-foreground/40",
      )}
      aria-hidden="true"
    />
  );
}

export default function ResearchPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [stages, setStages] = useState(initialStages);
  const [sourcesState, setSourcesState] = useState<ResearchSource[]>([]);
  const [progress, setProgress] = useState(0);
  const [sessionStatus, setSessionStatus] = useState<ResearchSession["status"]>("idle");
  const [artifacts, setArtifacts] = useState<ResearchSession["artifacts"]>([]);
  const [error, setError] = useState<string | null>(null);
  const [sourceTitle, setSourceTitle] = useState("");
  const [sourcePath, setSourcePath] = useState("");
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [selectedStage, setSelectedStage] = useState("ingest");
  const [dimension, setDimension] = useState("overview");
  const [showSources, setShowSources] = useState(true);
  const [runningAll, setRunningAll] = useState(false);
  const selected = useMemo(
    () => stages.find((item) => item.id === selectedStage) || stages[0],
    [selectedStage, stages],
  );

  useEffect(() => {
    api<ResearchSession>(`/projects/${projectId}/research`)
      .then((session) => {
        setStages(session.stages);
        setSourcesState(session.sources);
        setProgress(session.progress);
        setSessionStatus(session.status);
        setArtifacts(session.artifacts);
      })
      .catch((err: ApiError) => setError(err.message));
  }, [projectId]);

  useEffect(() => {
    if (sessionStatus !== "running") return;
    const timer = window.setInterval(() => {
      api<ResearchSession>(`/projects/${projectId}/research`)
        .then((session) => {
          setStages(session.stages);
          setSourcesState(session.sources);
          setProgress(session.progress);
          setSessionStatus(session.status);
          setArtifacts(session.artifacts);
        })
        .catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [projectId, sessionStatus]);

  async function startResearch() {
    try {
      const session = await api<ResearchSession>(`/projects/${projectId}/research/start`, { method: "POST", projectId });
      setStages(session.stages);
      setProgress(session.progress);
      setSessionStatus(session.status);
      setArtifacts(session.artifacts);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法启动分析");
    }
  }

  async function addSource(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sourceTitle.trim() && !sourceFile) return;
    try {
      const session = sourceFile
        ? await api<ResearchSession>(`/projects/${projectId}/research/upload`, {
          method: "POST",
          projectId,
          body: JSON.stringify({ title: sourceTitle.trim() || sourceFile.name.replace(/\.[^.]+$/, ""), filename: sourceFile.name, content: await sourceFile.text() }),
        })
        : await api<ResearchSession>(`/projects/${projectId}/research/sources`, {
        method: "POST",
        projectId,
        body: JSON.stringify({ title: sourceTitle.trim(), path: sourcePath.trim() || null }),
        });
      setSourcesState(session.sources);
      setSourceTitle("");
      setSourcePath("");
      setSourceFile(null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法登记参考作品");
    }
  }

  async function advanceStage() {
    const running = stages.find((item) => item.status === "running");
    if (!running) {
      await startResearch();
      return;
    }
    try {
      const session = await api<ResearchSession>(`/projects/${projectId}/research/stages/${running.id}`, {
        method: "POST",
        projectId,
        body: JSON.stringify({ status: "done", execute: true }),
      });
      setStages(session.stages);
      setProgress(session.progress);
      setSessionStatus(session.status);
      setArtifacts(session.artifacts);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法推进分析阶段");
    }
  }

  async function runRemainingStages() {
    setRunningAll(true);
    try {
      let currentStages = stages;
      while (true) {
        const stage = currentStages.find((item) => item.status === "running");
        if (!stage) break;
        const session = await api<ResearchSession>(`/projects/${projectId}/research/stages/${stage.id}`, {
          method: "POST",
          projectId,
          body: JSON.stringify({ status: "done", execute: true }),
        });
        currentStages = session.stages;
        setStages(session.stages);
        setSourcesState(session.sources);
        setProgress(session.progress);
        setSessionStatus(session.status);
        setArtifacts(session.artifacts);
        const next = currentStages.find((item) => item.status === "running");
        if (!next) break;
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "自动执行分析失败");
    } finally {
      setRunningAll(false);
    }
  }

  return (
    <section className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">Research Lab</p>
          <h1 className="text-2xl font-semibold tracking-tight">爆款小说研究</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            从参考作品中提取结构、节奏、文案和表达规律，再把抽象结果交给原创创作流程。
            这里展示的是分析过程，不把任何一本书直接当作写作模板。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className={cn(buttonVariants({ variant: "outline" }), "shrink-0")} onClick={advanceStage}>
            {sessionStatus === "idle" ? "开始分析" : "推进当前阶段"}
          </button>
          <button type="button" className={cn(buttonVariants(), "shrink-0")} onClick={runRemainingStages} disabled={runningAll || sessionStatus === "idle"}>
            {runningAll ? "自动分析中…" : "自动执行剩余阶段"}
          </button>
        </div>
      </header>

      <StatusBanner error={error} ok={!error ? `项目 ${projectId.slice(0, 8)} · 分析状态：${sessionStatus === "completed" ? "已完成" : sessionStatus === "running" ? "进行中" : "待启动"}` : null} />

      <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <div className="rounded-xl border bg-muted/20 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-semibold">分析管线</p>
                <p className="mt-1 text-xs text-muted-foreground">6 个阶段 · {stages.filter((item) => item.status === "done").length} 个已完成</p>
              </div>
              <span className="text-xs tabular-nums text-muted-foreground">{progress}%</span>
            </div>
            <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-foreground transition-all" style={{ width: `${progress}%` }} />
            </div>
          </div>

          <div className="space-y-1">
            {stages.map((stage, index) => (
              <button
                key={stage.id}
                type="button"
                onClick={() => setSelectedStage(stage.id)}
                className={cn(
                  "flex w-full items-start gap-3 rounded-lg px-3 py-3 text-left transition-colors hover:bg-muted/60",
                  selectedStage === stage.id && "bg-muted",
                )}
              >
                <StatusDot status={stage.status} />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center justify-between gap-2 text-sm font-medium">
                    <span>{index + 1}. {stage.title}</span>
                    <span className="text-[11px] font-normal text-muted-foreground">
                      {stage.status === "done" ? "完成" : stage.status === "running" ? "进行中" : "待处理"}
                    </span>
                  </span>
                  <span className="mt-1 block text-xs leading-5 text-muted-foreground">{stage.detail}</span>
                </span>
              </button>
            ))}
          </div>
        </aside>

        <div className="min-w-0 space-y-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">爆款参考作品</p><p className="mt-2 text-2xl font-semibold tabular-nums">{sourcesState.length}</p></div>
            <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">已生成研究产物</p><p className="mt-2 text-2xl font-semibold tabular-nums">{artifacts.length}</p></div>
            <div className="rounded-xl border p-4"><p className="text-xs text-muted-foreground">Profile 状态</p><p className="mt-2 text-2xl font-semibold tabular-nums">{artifacts.some((item) => item.id === "profile") ? "已生成" : "待生成"}</p></div>
          </div>

          <div className="rounded-xl border p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">当前节点</p>
                <h2 className="mt-1 text-lg font-semibold">{selected.title}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{selected.detail}</p>
              </div>
              <span className="rounded-full border px-2.5 py-1 text-xs text-muted-foreground">{selected.output}</span>
            </div>

            <div className="mt-5 border-t pt-4">
              <div className="flex flex-wrap gap-2">
                {dimensions.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setDimension(item.id)}
                    className={cn(
                      "rounded-md px-3 py-1.5 text-xs",
                      dimension === item.id ? "bg-foreground text-background" : "bg-muted text-muted-foreground hover:text-foreground",
                    )}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <div className="mt-5 grid gap-4 xl:grid-cols-[1.3fr_1fr]">
                <div className="rounded-lg bg-muted/40 p-4">
                  <p className="text-sm font-medium">{dimensions.find((item) => item.id === dimension)?.value}</p>
                  <div className="mt-4 space-y-4">
                    {(selected.status === "done" ? ["规律已由当前阶段产出，详见分析产物。"] : ["完成当前阶段后，这里会显示可追溯到参考作品的真实观察。"]).map((item, index) => (
                      <div key={item} className="flex items-start gap-3 text-sm">
                        <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-background text-xs tabular-nums">{index + 1}</span>
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="space-y-3">
                  <p className="text-sm font-medium">分析产物</p>
                  {artifacts.map((item) => (
                    <div key={item.title} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                      <span>{item.title}</span><span className="text-xs text-muted-foreground">{item.type || "预览"}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-xl border p-5">
            <button type="button" className="flex w-full items-center justify-between text-left" onClick={() => setShowSources((value) => !value)}>
              <span><span className="text-sm font-semibold">参考作品与证据</span><span className="ml-2 text-xs text-muted-foreground">每条规律都应能追溯到样本位置</span></span>
              <span className="text-xs text-muted-foreground">{showSources ? "收起" : "展开"}</span>
            </button>
            {showSources ? (
              <div className="mt-4 space-y-4">
                <form className="grid gap-2 rounded-lg bg-muted/30 p-3 md:grid-cols-[1fr_1fr_1fr_auto]" onSubmit={addSource}>
                  <input className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="参考作品名称" value={sourceTitle} onChange={(event) => setSourceTitle(event.target.value)} />
                  <input className="rounded-md border bg-background px-3 py-2 text-sm" placeholder="本地路径或来源备注（可选）" value={sourcePath} onChange={(event) => setSourcePath(event.target.value)} />
                  <input className="rounded-md border bg-background px-3 py-2 text-sm file:mr-2 file:border-0 file:bg-transparent file:text-xs" type="file" accept=".md,.markdown,.txt" onChange={(event) => setSourceFile(event.target.files?.[0] || null)} />
                  <button type="submit" className={cn(buttonVariants({ variant: "outline" }), "whitespace-nowrap")}>登记样本</button>
                </form>
                <div className="grid gap-3 md:grid-cols-3">
                  {sourcesState.map((source) => (
                    <div key={source.title} className="rounded-lg bg-muted/30 p-4">
                      <div className="flex items-start justify-between gap-2"><p className="text-sm font-medium">{source.title}</p><span className="text-[11px] text-muted-foreground">{source.status}</span></div>
                      <p className="mt-2 text-xs leading-5 text-muted-foreground">{source.author ? `${source.author} · ` : ""}{source.source_type} · {source.chapter_count} 章 · {source.word_count} 字</p>
                      {source.url || source.path ? <p className="mt-1 truncate text-xs text-muted-foreground">{source.url || source.path}</p> : null}
                      <p className="mt-3 text-xs text-muted-foreground">已登记的样本，分析结果会在阶段完成后显示</p>
                    </div>
                  ))}
                </div>
                {!sourcesState.length ? <div className="rounded-lg border border-dashed p-8 text-center"><p className="text-sm font-medium">还没有参考作品</p><p className="mt-1 text-xs text-muted-foreground">请登记你找到的爆款小说，或上传 Markdown/TXT 原文；系统不会用演示数据代替真实样本。</p></div> : null}
              </div>
            ) : null}
          </div>

          <div className="rounded-xl border border-dashed p-5">
            <p className="text-sm font-medium">下一步：创建原创创作提案</p>
            <p className="mt-1 text-sm text-muted-foreground">研究完成后，请进入“创建新书”，基于 Profile 生成并确认书名、简介和完整创作提案。</p>
          </div>
        </div>
      </div>
    </section>
  );
}
