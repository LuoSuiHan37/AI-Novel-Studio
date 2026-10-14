"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { confirmResource } from "@/lib/hitl";
import { approvalStatusLabel, characterRoleLabel } from "@/lib/labels";
import { evaluateAlphaNovelChecks } from "@/lib/platform-rules";
import type {
  Chapter,
  ChapterPlan,
  ChapterPlanSuggestion,
  Character,
  ContextPackPreview,
  Hook,
  MemoryItem,
  ScenePlan,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { ensureCharactersForPlan, ensureWriteReady } from "@/lib/write-path";

const REWRITE_OPS: { label: string; instruction: string }[] = [
  { label: "重写", instruction: "Rewrite this chapter in stronger close-third werewolf romance voice. Keep canon facts." },
  { label: "扩写", instruction: "Expand this chapter with more sensory pack-hall detail and interiority. Do not add new named characters." },
  { label: "缩写", instruction: "Shorten this chapter. Keep the rejection beat and the cliffhanger." },
  { label: "优化对话", instruction: "Improve dialogue only. Keep narration events the same." },
  { label: "加强情绪", instruction: "Increase emotional intensity of the mate-bond wound without melodrama." },
  { label: "加强浪漫", instruction: "Increase romantic tension and forbidden-pull while keeping the rejection." },
  { label: "加悬念结尾", instruction: "End on a sharper cliffhanger hook. Keep prior events." },
];

type ChapterPayload = { chapter: Chapter; plan: ChapterPlan | null; scenes: ScenePlan[] };
type ChapterVersion = {
  version: number;
  prose?: string | null;
  word_count: number;
  score: number | null;
  selected: boolean;
  accepted: boolean;
  rejection_reason?: string | null;
};
type RepetitionCheck = {
  status: string;
  blocked: boolean;
  max_similarity: number;
  matches: { chapter_number: number; similarity: number; repeated_paragraph_ratio: number; exact: boolean; reason: string }[];
};
type RelevanceCheck = {
  status: string;
  blocked: boolean;
  score: number;
  missing_requirements: string[];
  reason?: string | null;
};

export default function ChapterEditorPage() {
  const { projectId, chapterNo } = useParams<{ projectId: string; chapterNo: string }>();
  const number = Number(chapterNo);
  const [payload, setPayload] = useState<ChapterPayload | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [memory, setMemory] = useState<MemoryItem[]>([]);
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [draft, setDraft] = useState("");
  const [saved, setSaved] = useState("");
  const [preview, setPreview] = useState<string | null>(null);
  const [previewNote, setPreviewNote] = useState<string | null>(null);
  const [continuity, setContinuity] = useState<string | null>(null);
  const [planTitle, setPlanTitle] = useState("");
  const [planGoal, setPlanGoal] = useState("");
  const [planConflict, setPlanConflict] = useState("");
  const [planEmotion, setPlanEmotion] = useState("");
  const [planCliffhanger, setPlanCliffhanger] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [showTools, setShowTools] = useState(false);
  const [auditStage, setAuditStage] = useState<string | null>(null);
  const [auditStatus, setAuditStatus] = useState<string | null>(null);
  const [versions, setVersions] = useState<ChapterVersion[]>([]);
  const [repetitionCheck, setRepetitionCheck] = useState<RepetitionCheck | null>(null);
  const [relevanceCheck, setRelevanceCheck] = useState<RelevanceCheck | null>(null);
  const [contextPack, setContextPack] = useState<ContextPackPreview | null>(null);

  const dirty = draft !== saved;

  const load = useCallback(async () => {
    const [chapter, people, mem, hookList] = await Promise.all([
      api<ChapterPayload>(`/projects/${projectId}/chapters/${number}`),
      api<Character[]>(`/projects/${projectId}/characters`).catch(() => []),
      api<MemoryItem[]>(`/projects/${projectId}/memory`).catch(() => []),
      api<Hook[]>(`/projects/${projectId}/hooks`).catch(() => []),
    ]);
    setPayload(chapter);
    setCharacters(people);
    setMemory(mem);
    setHooks(hookList);
    setDraft(chapter.chapter.content || "");
    setSaved(chapter.chapter.content || "");
    const audit = chapter.chapter.extra_metadata?.audit as {
      status?: string;
      versions?: ChapterVersion[];
      repetition_check?: RepetitionCheck;
      relevance_check?: RelevanceCheck;
    } | undefined;
    setAuditStatus(audit?.status || null);
    setVersions(audit?.versions || []);
    setRepetitionCheck(audit?.repetition_check || null);
    setRelevanceCheck(audit?.relevance_check || null);
    setPlanTitle(
      chapter.plan?.chapter_title || (number === 1 ? "The Rejection" : `Untitled Chapter ${number}`),
    );
    setPlanGoal(chapter.plan?.chapter_goal || "");
    setPlanConflict(chapter.plan?.conflict || "");
    setPlanEmotion(chapter.plan?.emotional_arc || "");
    setPlanCliffhanger(chapter.plan?.cliffhanger || "");
    return chapter;
  }, [projectId, number]);

  useEffect(() => {
    load()
      .catch((err: ApiError) => setError(err.message))
      .finally(() => setLoading(false));
  }, [load]);

  const relevantMemory = useMemo(
    () => memory.filter((item) => !item.chapter_number || Math.abs((item.chapter_number || 0) - number) <= 3).slice(0, 8),
    [memory, number],
  );

  const platformChecks = useMemo(
    () =>
      evaluateAlphaNovelChecks({
        prose: draft,
        conflict: planConflict,
        emotionalArc: planEmotion,
        cliffhanger: planCliffhanger,
        chapterGoal: planGoal,
      }),
    [draft, planConflict, planEmotion, planCliffhanger, planGoal],
  );

  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label);
    setError(null);
    setOk(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : `${label}失败`);
    } finally {
      setBusy(null);
    }
  }

  const planStatus = payload?.plan?.status || "draft";
  const chapterStatus = payload?.chapter?.status || "draft";
  const chapterApproved = chapterStatus === "approved" || chapterStatus === "published";
  const manualReviewNeeded = !chapterApproved && (
    chapterStatus === "reviewed" ||
    auditStatus === "failed" ||
    auditStatus === "completed_with_errors" ||
    auditStatus === "not_configured" ||
    auditStatus === "passed"
  );
  const canGenerate = !dirty;

  async function ensurePlanApproved(): Promise<void> {
    let current = payload;
    const editedPlan = !!current?.plan && (
      planTitle !== current.plan.chapter_title ||
      planGoal !== current.plan.chapter_goal ||
      planConflict !== current.plan.conflict ||
      planEmotion !== current.plan.emotional_arc ||
      planCliffhanger !== current.plan.cliffhanger
    );
    const needsNewPlan =
      !current?.plan ||
      !current.scenes.length ||
      editedPlan;

    if (needsNewPlan) {
      let planBody: ChapterPlanSuggestion;
      if (!current?.plan || !current.scenes.length) {
        planBody = await api<ChapterPlanSuggestion>(
          `/projects/${projectId}/chapters/plan-suggestion`,
          {
            method: "POST",
            projectId,
            body: JSON.stringify({ chapter_number: number }),
          },
        );
      } else {
        planBody = {
          chapter_number: number,
          chapter_title: planTitle,
          pov: current.plan.pov,
          location: current.plan.location,
          characters: current.plan.characters,
          chapter_goal: planGoal,
          conflict: planConflict,
          emotional_arc: planEmotion,
          new_information: current.plan.new_information,
          reveal: current.plan.reveal,
          foreshadowing: current.plan.foreshadowing,
          setup: current.plan.setup,
          payoff: current.plan.payoff,
          cliffhanger: planCliffhanger,
          target_word_count: current.plan.target_word_count,
          target_word_min: current.plan.target_word_min,
          target_word_max: current.plan.target_word_max,
          scenes: current.scenes.map((scene) => ({
            scene_number: scene.scene_number,
            location: scene.location,
            characters: scene.characters,
            goal: scene.goal,
            conflict: scene.conflict,
            turning_point: scene.turning_point,
            dialogue_goal: scene.dialogue_goal,
            emotion: scene.emotion,
            information_revealed: scene.information_revealed,
            ending: scene.ending,
            target_word_count: scene.target_word_count,
            target_word_min: scene.target_word_min,
            target_word_max: scene.target_word_max,
          })),
        };
      }
      await api(`/projects/${projectId}/chapters/plan`, {
        method: "POST",
        projectId,
        body: JSON.stringify(planBody),
      });
      current = await load();
    }

    if (!current?.plan) {
      throw new ApiError(400, "invalid_state", "章节计划创建失败");
    }
    await ensureCharactersForPlan(projectId, current.plan.characters);
    if (current.plan.status !== "approved") {
      await confirmResource(
        `/projects/${projectId}/chapters/${number}/plan/submit`,
        `/projects/${projectId}/chapters/${number}/plan/approve`,
        projectId,
      );
      await load();
    }
  }

  async function generatePlan() {
    const suggestion = await api<ChapterPlanSuggestion>(
      `/projects/${projectId}/chapters/plan-suggestion`,
      {
        method: "POST",
        projectId,
        body: JSON.stringify({ chapter_number: number }),
      },
    );
    await api(`/projects/${projectId}/chapters/plan`, {
      method: "POST",
      projectId,
      body: JSON.stringify(suggestion),
    });
    await load();
    setOk("AI 章节计划已保存为新草稿版本。检查计划并批准后即可生成正文。");
  }

  async function previewContextPack() {
    const result = await api<ContextPackPreview>(
      `/projects/${projectId}/chapters/${number}/context-pack`,
      { projectId },
    );
    setContextPack(result);
  }

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">第 {number} 章工作台</h1>
          <p className="text-xs text-muted-foreground">
            计划状态：{approvalStatusLabel(planStatus)} ·{" "}
            {dirty ? "有未保存修改 — AI 不会覆盖正文，除非你应用预览。" : "已保存"}
          </p>
        </div>
      </div>
      <StatusBanner loading={loading} error={error} ok={ok} />
      {!loading ? (
        <p className={cn(
          "rounded-md border px-3 py-2 text-xs",
          chapterApproved
            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
            : manualReviewNeeded
            ? "border-amber-200 bg-amber-50 text-amber-700"
            : "bg-muted/30 text-muted-foreground",
        )}>
          {chapterApproved
            ? "自动流程已完成：章节已批准，章节摘要、场景交接和人物认知已自动沉淀到故事记忆。"
            : manualReviewNeeded
            ? "自动流程需要人工兜底：请根据下方审查结果修订或确认本章。"
            : "正常流程：生成正文后系统会自动执行审查；只有审查未通过时才需要人工处理。"}
        </p>
      ) : null}
      {!loading && characters.length === 0 ? (
        <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          还没有角色。生成章节计划后，计划中出现的人物会逐个自动加入本书角色库。
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          disabled={!!busy || dirty}
          onClick={() => void run("AI 生成章节计划", generatePlan)}
        >
          AI 生成/重做计划
        </Button>
        <Button
          size="sm"
          disabled={!!busy || !canGenerate}
          title={dirty ? "请先保存或丢弃本地修改" : "缺角色或计划时会自动补齐，再生成正文预览"}
          onClick={() =>
            void run("生成本章", async () => {
              setAuditStatus("processing");
              setVersions([]);
              setAuditStage("准备章节上下文");
              await ensureWriteReady(projectId, number);
              await load();
              await ensurePlanApproved();
              setAuditStage("生成正文并执行独立审查");
              const result = await api<{
                writer: { title: string; prose: string };
                editor: { overall_notes: string; needs_human_review: boolean };
                continuity: { overall: string; findings: { problem: string; recommendation: string }[] };
                revision_suggestion: { change_summary: string } | null;
                review_status: string;
                versions: ChapterVersion[];
                length_ok: boolean;
                length_warning: string | null;
                repetition_check: RepetitionCheck;
                relevance_check: RelevanceCheck;
                auto_approved: boolean;
              }>(
                `/projects/${projectId}/chapters/${number}/generate`,
                {
                  method: "POST",
                  projectId,
                  body: JSON.stringify({ persist: true, human_notes: "Write the planned chapter." }),
                },
              );
              setAuditStage(
                result.review_status === "completed"
                  ? "独立审查完成，已选择最佳版本"
                  : result.review_status === "completed_with_errors"
                  ? "独立审查完成，但发现问题，等待修订"
                  : "未执行独立审查，仅生成 V1 草稿"
              );
              setAuditStatus(result.review_status);
              setVersions(result.versions || []);
              setRepetitionCheck(result.repetition_check);
              setRelevanceCheck(result.relevance_check);
              setPreview(result.writer.prose);
              const checks = [
                `编辑检查：${result.editor.overall_notes}`,
                `一致性：${result.continuity.overall}${result.continuity.findings.length ? `（${result.continuity.findings.map((item) => item.problem).join("；")}）` : ""}`,
                result.revision_suggestion
                  ? `已按检查意见自动修订：${result.revision_suggestion.change_summary}`
                  : "检查未发现需要自动修订的问题",
              ].join(" · ");
              setContinuity(checks);
              const repetitionNote = result.repetition_check.blocked
                ? `重复检查阻断：${result.repetition_check.matches.map((item) => `与第 ${item.chapter_number} 章${item.reason}`).join("；")}`
                : "重复检查通过";
              const relevanceNote = result.relevance_check?.blocked
                ? `计划相关性阻断：${result.relevance_check.missing_requirements.join("；")}`
                : "计划相关性检查通过";
              setPreviewNote(
                `AI 正文《${result.writer.title}》已保存。${result.length_warning ? `${result.length_warning} ` : ""}${repetitionNote}；${relevanceNote}。${checks}`,
              );
              if (result.auto_approved) {
                await load();
                setOk(result.length_warning ? `${result.length_warning}章节已自动审核并批准。` : "章节已自动生成、审核并批准。" );
              } else if (result.review_status === "completed" && !result.repetition_check.blocked && !result.relevance_check?.blocked) {
                setAuditStage("自动独立审查并批准章节");
                await api(`/projects/${projectId}/chapters/${number}/review`, { method: "POST", projectId });
                await api(`/projects/${projectId}/chapters/${number}/approve`, {
                  method: "POST",
                  projectId,
                  body: JSON.stringify({ confirmed_by: "system-auto" }),
                });
                await load();
                setOk(result.length_warning ? `${result.length_warning}章节已自动审核并批准。` : "章节已自动生成、审核并批准。" );
              } else {
                setOk("章节已保存，但自动审核未通过；系统已暂停批准并保留问题记录。" );
              }
            })
          }
        >
          {busy === "生成本章" ? "生成中…" : "生成本章"}
        </Button>
        {manualReviewNeeded ? <span className="self-center text-xs text-amber-700">人工兜底</span> : null}
        {manualReviewNeeded && chapterStatus !== "reviewed" ? <Button
          size="sm"
          variant="outline"
          disabled={!!busy || dirty || !draft.trim()}
          onClick={() =>
            void run("完成审查", async () => {
              const result = await api<{
                chapter: Chapter;
                reviewed?: boolean;
                review_status?: string;
                continuity?: { overall: string; findings: { problem: string }[] };
              }>(`/projects/${projectId}/chapters/${number}/review`, { method: "POST", projectId });
              setAuditStatus(result.review_status || (result.reviewed ? "passed" : "failed"));
              setAuditStage(result.reviewed ? "审查通过，可以批准章节" : "审查未通过，请根据问题修订正文");
              setContinuity(
                result.continuity
                  ? `${result.continuity.overall}${result.continuity.findings.length ? `：${result.continuity.findings.map((item) => item.problem).join("；")}` : ""}`
                  : null,
              );
              await load();
              setOk(result.reviewed ? "章节审查通过，现在可以批准章节。" : "章节审查未通过，请先修订正文。 ");
            })
          }
        >
          {busy === "完成审查" ? "审查中…" : "完成审查"}
        </Button> : null}
        {manualReviewNeeded ? <Button
          size="sm"
          disabled={!!busy || chapterStatus !== "reviewed"}
          title={chapterStatus !== "reviewed" ? "请先完成审查并通过" : "批准后才会写入长期故事记忆"}
          onClick={() =>
            void run("批准章节", async () => {
              await api(`/projects/${projectId}/chapters/${number}/approve`, {
                method: "POST",
                projectId,
                body: JSON.stringify({ confirmed_by: "studio-user" }),
              });
              await load();
              setOk("章节已批准，摘要、场景交接和人物认知已写入长期记忆。 ");
              setAuditStage("章节已批准，长期记忆已沉淀");
            })
          }
        >
          批准章节
        </Button> : null}
        <Button
          size="sm"
          variant="outline"
          disabled={!!busy}
          onClick={() => void run("预览上下文", previewContextPack)}
        >
          预览生成上下文
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={!!busy || !dirty}
          onClick={() =>
            void run("保存", async () => {
              await api(`/projects/${projectId}/chapters/${number}`, {
                method: "PATCH",
                projectId,
                body: JSON.stringify({ content: draft, title: planTitle, audit: null }),
              });
              setSaved(draft);
              setAuditStatus(null);
              setAuditStage("正文已修改，等待重新独立审查");
              setVersions([]);
              setOk("已保存为新修订版本。");
            })
          }
        >
          保存
        </Button>
        <Button size="sm" variant="ghost" disabled={!!busy} onClick={() => setShowTools((value) => !value)}>
          {showTools ? "收起改稿工具" : "改稿工具"}
        </Button>
      </div>

      {showTools ? (
        <div className="flex flex-wrap gap-2 rounded-lg border bg-muted/20 p-3">
          {REWRITE_OPS.map((op) => (
            <Button
              key={op.label}
              size="sm"
              variant="outline"
              disabled={!!busy || !draft.trim()}
              onClick={() =>
                void run(op.label, async () => {
                  const result = await api<{ prose: string; change_summary: string }>(
                    `/projects/${projectId}/chapters/${number}/propose-edit`,
                    {
                      method: "POST",
                      projectId,
                      body: JSON.stringify({ instruction: op.instruction, source_prose: draft, persist: false }),
                    },
                  );
                  setPreview(result.prose);
                  setPreviewNote(result.change_summary || op.label);
                })
              }
            >
              {op.label}
            </Button>
          ))}
          <Button
            size="sm"
            variant="outline"
            disabled={!!busy || !draft.trim()}
            onClick={() =>
              void run("一致性检查", async () => {
                if (dirty) {
                  setError("一致性检查读取已保存正文，请先保存或丢弃本地修改。");
                  return;
                }
                const result = await api<{
                  continuity: { overall: string; findings: { problem: string }[] };
                  review_status: string;
                }>(
                  `/projects/${projectId}/chapters/${number}/continuity`,
                  { method: "POST", projectId },
                );
                const findings = result.continuity.findings.map((item) => item.problem).join(" · ");
                setContinuity(`${result.continuity.overall}${findings ? `: ${findings}` : ""}`);
                setAuditStatus(result.review_status);
                setAuditStage(
                  result.review_status === "failed"
                    ? "一致性检查发现问题，等待修订"
                    : "一致性检查完成；批准前仍需完整独立审查"
                );
              })
            }
          >
            一致性检查
          </Button>
        </div>
      ) : null}

      {busy ? <p className="text-xs text-muted-foreground">{busy}… {auditStage || "正在处理"}</p> : null}

      {contextPack ? (
        <section className="space-y-2 rounded-lg border bg-muted/20 p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-medium">本章生成上下文预览</h2>
            <Button size="sm" variant="ghost" onClick={() => setContextPack(null)}>关闭</Button>
          </div>
          <p className="text-xs text-muted-foreground">
            第 {contextPack.chapter_number} 章 · 预计上下文 {contextPack.memory_package.token_estimate} tokens
            {contextPack.memory_package.dropped_for_budget
              ? ` · 因预算省略 ${contextPack.memory_package.dropped_for_budget} 项`
              : " · 未省略记忆"}
          </p>
          <div className="grid gap-2 md:grid-cols-3">
            <div className="rounded-md border bg-background p-2">
              <p className="text-xs font-medium">当前故事弧</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {contextPack.story_arc
                  ? `${contextPack.story_arc.title}（${contextPack.story_arc.start_chapter_number}-${contextPack.story_arc.end_chapter_number}）`
                  : "未匹配故事弧"}
              </p>
            </div>
            <div className="rounded-md border bg-background p-2">
              <p className="text-xs font-medium">未解决钩子</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {contextPack.memory_package.unresolved_hooks.length
                  ? contextPack.memory_package.unresolved_hooks.join("；")
                  : "暂无"}
              </p>
            </div>
            <div className="rounded-md border bg-background p-2">
              <p className="text-xs font-medium">禁止知识</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {Object.keys(contextPack.context.forbidden_knowledge).length
                  ? Object.entries(contextPack.context.forbidden_knowledge)
                      .map(([name, facts]) => `${name}：${facts.join("、")}`)
                      .join("；")
                  : "暂无"}
              </p>
            </div>
          </div>
          <details>
            <summary className="cursor-pointer text-xs font-medium">查看带入记忆与伏笔</summary>
            <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-background p-2 text-xs">
              {contextPack.visible_text}
            </pre>
          </details>
        </section>
      ) : null}

      {auditStage || versions.length || auditStatus || repetitionCheck || relevanceCheck ? (
        <section className="space-y-2 rounded-lg border bg-muted/20 p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-medium">章节审查流程</h2>
            <span className={cn(
              "rounded-full px-2 py-1 text-xs",
              auditStatus === "completed" || auditStatus === "passed"
                ? "bg-emerald-100 text-emerald-700"
                : auditStatus === "failed" || auditStatus === "completed_with_errors"
                ? "bg-rose-100 text-rose-700"
                : "bg-amber-100 text-amber-700",
            )}>
              {auditStatus === "completed"
                ? "独立审查完成"
                : auditStatus === "completed_with_errors"
                ? "审查发现问题"
                : auditStatus === "passed"
                ? "审查通过"
                : auditStatus === "failed"
                ? "审查未通过"
                : auditStatus === "not_configured"
                ? "未配置独立审查"
                : "处理中"}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {auditStage || "生成后会在这里显示审查和版本选择结果。"}
          </p>
          {auditStatus === "not_configured" ? (
            <p className="text-xs text-amber-700">请在 AI 设置中配置与生成模型不同的审查模型，章节才能批准。</p>
          ) : null}
          {repetitionCheck?.blocked ? (
            <p className="text-xs text-red-700">
              重复检查已阻断：{repetitionCheck.matches.map((item) => `第 ${item.chapter_number} 章（${item.reason}）`).join("、")}。修改正文后才能审核和批准。
            </p>
          ) : repetitionCheck ? (
            <p className="text-xs text-emerald-700">重复检查通过，未发现需要阻断的历史章节重复。</p>
          ) : null}
          {relevanceCheck?.blocked ? (
            <p className="text-xs text-red-700">
              计划相关性检查已阻断：{relevanceCheck.missing_requirements.join("、")}。修改正文使其完成本章计划后才能审核和批准。
            </p>
          ) : relevanceCheck ? (
            <p className="text-xs text-emerald-700">计划相关性检查通过（评分 {relevanceCheck.score}）。</p>
          ) : null}
          {versions.length ? (
            <div className="grid gap-2 md:grid-cols-3">
              {versions.map((item) => (
                <div key={item.version} className={cn("rounded-md border p-2 text-xs", item.selected && "border-emerald-500 bg-emerald-50")}>
                  <div className="flex justify-between font-medium">
                    <span>V{item.version}</span>
                    <span>{item.selected ? "已选择" : item.accepted ? "候选" : "已淘汰"}</span>
                  </div>
                  <p className="text-muted-foreground">{item.score === null ? "未评分" : `评分 ${item.score.toFixed(1)}`} · {item.word_count} 词</p>
                  {item.rejection_reason ? <p className="mt-1 text-rose-700">{item.rejection_reason}</p> : null}
                  {item.prose ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="mt-1 h-7 px-1 text-xs"
                      onClick={() => {
                        setPreview(item.prose || null);
                        setPreviewNote(`V${item.version} 版本正文（查看后可选择应用）`);
                      }}
                    >
                      查看正文
                    </Button>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="grid min-h-[70vh] gap-3 lg:grid-cols-[240px_minmax(0,1fr)_260px]">
        <aside className="space-y-3 rounded-lg border p-3 text-sm">
          <h2 className="font-medium">章节计划</h2>
          <p className="text-xs text-muted-foreground">正文生成会严格参考已批准的计划；修改计划字段后，生成正文时会保存为新草稿并要求重新批准。</p>
          <Field label="标题" value={planTitle} onChange={setPlanTitle} />
          <Field label="目标" value={planGoal} onChange={setPlanGoal} multiline rows={3} />
          <Field label="冲突" value={planConflict} onChange={setPlanConflict} multiline rows={3} />
          <Field label="情绪弧" value={planEmotion} onChange={setPlanEmotion} multiline rows={2} />
          <Field label="章末钩子" value={planCliffhanger} onChange={setPlanCliffhanger} multiline rows={2} />
          <h2 className="pt-2 font-medium">
            场景计划
            {payload?.plan?.target_word_count ? ` · 目标 ${payload.plan.target_word_count} 字` : ""}
          </h2>
          {(payload?.scenes || []).map((scene) => (
            <div key={scene.id} className="rounded-md bg-muted/40 p-2 text-xs">
              <div className="font-medium">
                场景 {scene.scene_number} · {scene.location}
                {scene.target_word_count ? ` · ${scene.target_word_min}-${scene.target_word_max} 字` : ""}
              </div>
              <p>{scene.goal}</p>
            </div>
          ))}
          {!payload?.scenes?.length ? (
            <p className="text-xs text-muted-foreground">尚无场景；生成本章时会自动创建。</p>
          ) : null}
        </aside>

        <div className="flex min-w-0 flex-col gap-2">
          <textarea
            className="min-h-[420px] flex-1 rounded-lg border border-input bg-background p-3 font-mono text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="在此撰写或粘贴章节正文。除非你点击「应用预览」，AI 不会覆盖此框内容。"
          />
          {preview ? (
            <div className="rounded-lg border p-3">
              <div className="mb-2 text-xs text-muted-foreground">{previewNote}</div>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-sm">{preview}</pre>
              <div className="mt-2 flex gap-2">
                <Button
                  size="sm"
                  onClick={() => {
                    setDraft(preview);
                    setPreview(null);
                    setOk("预览已应用到编辑器。请保存以创建修订版本。");
                  }}
                >
                  应用预览
                </Button>
                <Button size="sm" variant="outline" onClick={() => setPreview(null)}>
                  丢弃
                </Button>
              </div>
            </div>
          ) : null}
        </div>

        <aside className="space-y-3 rounded-lg border p-3 text-sm">
          <h2 className="font-medium">AlphaNovel 检查</h2>
          <ul className="space-y-1.5 text-xs">
            {platformChecks.map((item) => (
              <li key={item.id}>
                <span className={item.ok ? "text-foreground" : "text-muted-foreground"}>
                  {item.ok ? "✓" : "○"} {item.label}
                </span>
                <div className="text-muted-foreground">{item.detail}</div>
              </li>
            ))}
          </ul>
          <h2 className="font-medium">角色</h2>
          {characters.map((item) => (
            <div key={item.id} className="text-xs">
              <span className="font-medium">{item.name}</span> · {characterRoleLabel(item.role)}
            </div>
          ))}
          {!characters.length ? (
            <p className="text-xs text-muted-foreground">
              暂无角色。{" "}
              <Link
                href={`/projects/${projectId}/characters`}
                className={cn(buttonVariants({ variant: "link" }), "h-auto p-0 text-xs")}
              >
                去创建
              </Link>
            </p>
          ) : null}
          <h2 className="font-medium">相关记忆</h2>
          {relevantMemory.map((item) => (
            <p key={item.id} className="text-xs text-muted-foreground">
              {item.content}
            </p>
          ))}
          {!relevantMemory.length ? <p className="text-xs text-muted-foreground">暂无近章记忆。</p> : null}
          <h2 className="font-medium">一致性</h2>
          <p className="text-xs text-muted-foreground">{continuity || "在改稿工具里可运行一致性检查。"}</p>
          <h2 className="font-medium">钩子</h2>
          {hooks.map((item) => (
            <p key={item.id} className="text-xs">
              {item.description}
            </p>
          ))}
          {!hooks.length ? <p className="text-xs text-muted-foreground">批准章节后沉淀钩子。</p> : null}
        </aside>
      </div>
    </section>
  );
}
