"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusBanner } from "@/components/ui-bits";
import { ApiError } from "@/lib/api";
import { ensureWriteReady } from "@/lib/write-path";

export default function WriteRedirectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    ensureWriteReady(projectId)
      .then((href) => {
        if (!cancelled) router.replace(href);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "无法进入写作页");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, router]);

  return (
    <section className="mx-auto max-w-lg space-y-3">
      <h1 className="text-xl font-semibold">正在打开写作页…</h1>
      <p className="text-sm text-muted-foreground">
        不需要预先创建所有配角；先准备本书当前剧情需要的角色，章节计划引入的新角色会自动加入角色库。
      </p>
      <StatusBanner loading={!error} error={error} />
    </section>
  );
}
