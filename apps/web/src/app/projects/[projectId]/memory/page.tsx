"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { epistemicStatusLabel, importanceLabel, memoryLayerLabel } from "@/lib/labels";
import type { MemoryItem } from "@/lib/types";

export default function MemoryPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<MemoryItem[]>(`/projects/${projectId}/memory`)
      .then(setItems)
      .catch((err: ApiError) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-semibold">故事记忆</h1>
      <p className="text-sm text-muted-foreground">
        资料库审计视图。写作时请在章节编辑器侧栏查看相关记忆。
      </p>
      <StatusBanner loading={loading} error={error} />
      {items.map((item) => (
        <article key={item.id} className="rounded-lg border p-3 text-sm">
          <div className="text-xs text-muted-foreground">
            {memoryLayerLabel(item.layer)} · {epistemicStatusLabel(item.epistemic_status)} ·{" "}
            {importanceLabel(item.importance)}
          </div>
          <p>{item.content}</p>
        </article>
      ))}
      {!loading && items.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无已确认的记忆。</p>
      ) : null}
    </section>
  );
}
