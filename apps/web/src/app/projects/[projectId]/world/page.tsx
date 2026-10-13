"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Field, StatusBanner } from "@/components/ui-bits";
import { api, ApiError } from "@/lib/api";
import { confirmResource, tryAdvancePipeline } from "@/lib/hitl";
import { approvalStatusLabel } from "@/lib/labels";
import type { WorldBible } from "@/lib/types";
import { cn } from "@/lib/utils";

export default function WorldPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [name, setName] = useState("Moonridge Pack");
  const [summary, setSummary] = useState("Mountain pack under an Alpha King. Mate bonds can be publicly rejected.");
  const [rule, setRule] = useState("A public rejection before the pack severs Luna rank.");
  const [status, setStatus] = useState("draft");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<WorldBible>(`/projects/${projectId}/world`)
      .then((world) => {
        setName(world.name);
        setSummary(world.summary);
        setStatus(world.status);
        if (world.rules[0]) setRule(world.rules[0].description);
      })
      .catch(() => undefined)
      .finally(() => setLoading(false));
  }, [projectId]);

  async function saveAndConfirm() {
    setBusy(true);
    setError(null);
    try {
      const saved = await api<WorldBible>(`/projects/${projectId}/world`, {
        method: "PATCH",
        projectId,
        body: JSON.stringify({
          name,
          summary,
          factions: ["Moonridge Pack"],
          rules: [{ name: "Public rejection", category: "mate_bond", description: rule, is_hard_constraint: true }],
        }),
      });
      setStatus(saved.status);
      if (saved.status !== "approved") {
        await confirmResource(`/projects/${projectId}/world/submit`, `/projects/${projectId}/world/approve`, projectId);
        const world = await api<WorldBible>(`/projects/${projectId}/world`);
        setStatus(world.status);
      }
      await tryAdvancePipeline(projectId);
      setOk("世界观已保存，已自动确定。可回概览看下一步。");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "保存失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="max-w-3xl space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">世界观</h1>
          <p className="text-sm text-muted-foreground">状态：{approvalStatusLabel(status)} · 点一次即可过门禁</p>
        </div>
        <Link href={`/projects/${projectId}`} className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "inline-flex")}>
          回概览
        </Link>
      </div>
      <StatusBanner loading={loading} error={error} ok={ok} />
      <Field label="名称" value={name} onChange={setName} />
      <Field label="摘要" value={summary} onChange={setSummary} multiline rows={4} />
      <Field label="硬性规则" value={rule} onChange={setRule} multiline />
      <Button disabled={busy} onClick={() => void saveAndConfirm()}>
        {busy ? "保存中…" : "保存"}
      </Button>
    </section>
  );
}
