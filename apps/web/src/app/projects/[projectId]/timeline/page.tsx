"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import type { TimelineItem } from "@/lib/types";

export default function TimelinePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [items, setItems] = useState<TimelineItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<TimelineItem[]>(`/projects/${projectId}/timeline`)
      .then(setItems)
      .catch((err: ApiError) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  return (
    <section className="space-y-3">
      <h1 className="text-2xl font-semibold">时间线</h1>
      <p className="text-sm text-muted-foreground">资料库审计视图 · 章节批准后由流水线沉淀。</p>
      <StatusBanner loading={loading} error={error} />
      {items.map((item) => (
        <div key={item.id} className="rounded-lg border px-3 py-2 text-sm">
          <span className="font-medium">{item.sequence}.</span> {item.in_world_time} · {item.title}
          <div className="text-muted-foreground">{item.description}</div>
        </div>
      ))}
      {!loading && items.length === 0 ? (
        <p className="text-sm text-muted-foreground">暂无时间线事件。</p>
      ) : null}
    </section>
  );
}
