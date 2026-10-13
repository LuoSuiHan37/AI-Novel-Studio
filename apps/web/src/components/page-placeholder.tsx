export function PagePlaceholder({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <section className="max-w-3xl space-y-3">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="text-sm text-muted-foreground">{description}</p>
      <p className="rounded-lg border bg-muted/40 px-3 py-2 text-sm">
        Skeleton only. No generation or editing workflows in STEP 2.
      </p>
    </section>
  );
}
