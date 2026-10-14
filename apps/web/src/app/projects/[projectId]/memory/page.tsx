"use client";

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { StatusBanner } from "@/components/ui-bits";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { epistemicStatusLabel, importanceLabel, memoryLayerLabel } from "@/lib/labels";
import type { MemoryItem } from "@/lib/types";

export default function MemoryPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [backfilling, setBackfilling] = useState(false);
  const [backfillMessage, setBackfillMessage] = useState<string | null>(null);
  const [preflight, setPreflight] = useState<{
    read_only: boolean;
    safe_to_backfill: boolean;
    total_chapters: number;
    approved_chapters: number[];
    missing_memory: number[];
    blockers: string[];
  } | null>(null);
  const [query, setQuery] = useState("");
  const [layerFilter, setLayerFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [chapterFilter, setChapterFilter] = useState("all");

  useEffect(() => {
    api<MemoryItem[]>(`/projects/${projectId}/memory`)
      .then(setItems)
      .catch((err: ApiError) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  async function backfill() {
    setBackfilling(true);
    setBackfillMessage(null);
    try {
      const result = await api<{
        processed: number[];
        already_present: number[];
        skipped: { chapter_number: number; reason: string }[];
        errors: { chapter_number: number; reason: string }[];
      }>(`/projects/${projectId}/memory/backfill`, { method: "POST", projectId });
      setBackfillMessage(
        `已处理 ${result.processed.length} 章，已有 ${result.already_present.length} 章，跳过 ${result.skipped.length} 章，失败 ${result.errors.length} 章。`,
      );
      const refreshed = await api<MemoryItem[]>(`/projects/${projectId}/memory`);
      setItems(refreshed);
    } catch (err) {
      setBackfillMessage(err instanceof ApiError ? err.message : "历史记忆回填失败");
    } finally {
      setBackfilling(false);
    }
  }

  async function checkPreflight() {
    const result = await api<typeof preflight>(`/projects/${projectId}/memory/preflight`);
    setPreflight(result);
  }

  const chapters = useMemo(
    () => Array.from(new Set(items.map((item) => item.chapter_number).filter((item): item is number => item !== null))).sort((a, b) => a - b),
    [items],
  );
  const layers = useMemo(() => Array.from(new Set(items.map((item) => item.layer))).sort(), [items]);
  const types = useMemo(() => Array.from(new Set(items.map((item) => item.memory_type))).sort(), [items]);
  const filteredItems = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((item) => {
      if (layerFilter !== "all" && item.layer !== layerFilter) return false;
      if (typeFilter !== "all" && item.memory_type !== typeFilter) return false;
      if (chapterFilter !== "all" && String(item.chapter_number) !== chapterFilter) return false;
      return !needle || item.content.toLowerCase().includes(needle);
    });
  }, [chapterFilter, items, layerFilter, query, typeFilter]);

  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-semibold">故事记忆</h1>
      <p className="text-sm text-muted-foreground">
        资料库审计视图。新章节审查通过后会自动沉淀记忆；本页的回填功能只用于处理历史章节。
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" variant="ghost" disabled={backfilling} onClick={() => void checkPreflight()}>
          检查真实数据
        </Button>
        <Button size="sm" variant="outline" disabled={backfilling} onClick={() => void backfill()}>
          {backfilling ? "正在回填历史章节…" : "回填历史章节记忆"}
        </Button>
        <p className="text-xs text-muted-foreground">
          只处理已批准且尚未建立结构化记忆的章节，不会修改正文。
        </p>
      </div>
      {preflight ? (
        <div className="rounded-lg border bg-muted/20 p-3 text-xs">
          <p className={preflight.safe_to_backfill ? "text-emerald-700" : "text-amber-700"}>
            只读检查：{preflight.safe_to_backfill ? "可以回填" : "暂不建议回填"}
          </p>
          <p className="mt-1 text-muted-foreground">
            共 {preflight.total_chapters} 章 · 已确认 {preflight.approved_chapters.length} 章 · 缺少记忆 {preflight.missing_memory.length} 章
          </p>
          {preflight.blockers.length ? <p className="mt-1 text-amber-700">{preflight.blockers.join("；")}</p> : null}
        </div>
      ) : null}
      {backfillMessage ? <p className="text-xs text-muted-foreground">{backfillMessage}</p> : null}
      <div className="grid gap-2 rounded-lg border bg-muted/20 p-3 md:grid-cols-4">
        <input
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索记忆内容…"
        />
        <select className="h-9 rounded-md border border-input bg-background px-2 text-sm" value={chapterFilter} onChange={(event) => setChapterFilter(event.target.value)}>
          <option value="all">全部章节</option>
          {chapters.map((chapter) => <option key={chapter} value={chapter}>第 {chapter} 章</option>)}
        </select>
        <select className="h-9 rounded-md border border-input bg-background px-2 text-sm" value={layerFilter} onChange={(event) => setLayerFilter(event.target.value)}>
          <option value="all">全部记忆层</option>
          {layers.map((layer) => <option key={layer} value={layer}>{memoryLayerLabel(layer)}</option>)}
        </select>
        <select className="h-9 rounded-md border border-input bg-background px-2 text-sm" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}>
          <option value="all">全部类型</option>
          {types.map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
      </div>
      <p className="text-xs text-muted-foreground">显示 {filteredItems.length} / {items.length} 条记忆</p>
      <StatusBanner loading={loading} error={error} />
      {filteredItems.map((item) => (
        <article key={item.id} className="rounded-lg border p-3 text-sm">
          <div className="text-xs text-muted-foreground">
            {memoryLayerLabel(item.layer)} · {epistemicStatusLabel(item.epistemic_status)} ·{" "}
            {importanceLabel(item.importance)}
          </div>
          <p>{item.content}</p>
          {item.extra_metadata?.scene_handoffs?.length ? (
            <div className="mt-3 space-y-2 border-t pt-2 text-xs text-muted-foreground">
              <p className="font-medium text-foreground">场景交接</p>
              {item.extra_metadata.scene_handoffs.map((handoff, index) => (
                <div key={`${item.id}-handoff-${index}`} className="rounded bg-muted/40 p-2">
                  <p>
                    场景 {handoff.scene_number ?? index + 1}：{handoff.what_happened || "未提取事件"}
                  </p>
                  {handoff.open_questions?.length ? <p>待解问题：{handoff.open_questions.join("；")}</p> : null}
                  {handoff.next_scene_requirements?.length ? (
                    <p>下一场要求：{handoff.next_scene_requirements.join("；")}</p>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
          {item.extra_metadata?.memory_validation?.findings?.length ? (
            <p className="mt-2 text-xs text-amber-700">
              记忆校验：{item.extra_metadata.memory_validation.findings.length} 条提示，建议复核场景交接。
            </p>
          ) : null}
        </article>
      ))}
      {!loading && filteredItems.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无已确认的记忆。</p>
      ) : null}
    </section>
  );
}
