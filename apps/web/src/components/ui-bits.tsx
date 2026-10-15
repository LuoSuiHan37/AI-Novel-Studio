import { useState } from "react";

export function StatusBanner({
  loading,
  error,
  ok,
}: {
  loading?: boolean;
  error?: string | null;
  ok?: string | null;
}) {
  if (loading) {
    return (
      <p className="rounded-md border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
        加载中…
      </p>
    );
  }
  if (error) {
    return (
      <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        {error}
      </p>
    );
  }
  if (ok) {
    return (
      <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm text-muted-foreground">{ok}</p>
    );
  }
  return null;
}

export function Field({
  label,
  value,
  onChange,
  multiline,
  rows = 3,
  readOnly,
  type = "text",
  allowReveal = false,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  multiline?: boolean;
  rows?: number;
  readOnly?: boolean;
  type?: "text" | "password";
  allowReveal?: boolean;
  hint?: string;
}) {
  const [revealed, setRevealed] = useState(false);
  const cls =
    "w-full rounded-md border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50";
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {multiline ? (
        <textarea className={cls} rows={rows} value={value} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <div className="flex gap-2">
          <input
            type={type === "password" && !revealed ? "password" : "text"}
            autoComplete={type === "password" ? "new-password" : undefined}
            className={cls}
            value={value}
            readOnly={readOnly}
            onChange={(e) => onChange(e.target.value)}
          />
          {type === "password" && allowReveal ? (
            <button
              type="button"
              className="rounded-md border px-3 text-xs whitespace-nowrap hover:bg-muted"
              onClick={() => setRevealed((current) => !current)}
            >
              {revealed ? "隐藏" : "显示"}
            </button>
          ) : null}
        </div>
      )}
      {hint ? <span className="block text-xs text-muted-foreground">{hint}</span> : null}
    </label>
  );
}
