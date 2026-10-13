"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { foreshadowStatusLabel, hookStatusLabel, hookTypeLabel } from "@/lib/labels";
import type { Foreshadowing, Hook } from "@/lib/types";

export default function HooksPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [hooks, setHooks] = useState<Hook[]>([]);
  const [items, setItems] = useState<Foreshadowing[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api<Hook[]>(`/projects/${projectId}/hooks`),
      api<Foreshadowing[]>(`/projects/${projectId}/foreshadowing`),
    ])
      .then(([hookList, foreshadow]) => {
        setHooks(hookList);
        setItems(foreshadow);
      })
      .catch((err: ApiError) => setError(err.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  return (
    <section className="grid gap-6 md:grid-cols-2">
      <div className="space-y-3">
        <h1 className="text-2xl font-semibold">钩子</h1>
        <p className="text-sm text-muted-foreground">资料库审计 · 写作时见章节侧栏。</p>
        <StatusBanner loading={loading} error={error} />
        {hooks.map((item) => (
          <article key={item.id} className="rounded-lg border p-3 text-sm">
            <div className="text-xs text-muted-foreground">
              {hookTypeLabel(item.hook_type)} · {hookStatusLabel(item.status)}
            </div>
            {item.description}
          </article>
        ))}
      </div>
      <div className="space-y-3">
        <h2 className="text-xl font-semibold">伏笔</h2>
        {items.map((item) => (
          <article key={item.id} className="rounded-lg border p-3 text-sm">
            <div className="text-xs text-muted-foreground">{foreshadowStatusLabel(item.status)}</div>
            {item.description}
          </article>
        ))}
      </div>
    </section>
  );
}
