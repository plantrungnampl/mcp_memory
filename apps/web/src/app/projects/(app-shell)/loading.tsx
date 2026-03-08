export default function Loading() {
  return (
    <section aria-busy="true" aria-live="polite" className="space-y-4" role="status">
      <span className="sr-only">Loading projects content</span>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="h-20 animate-pulse rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
        <div className="h-20 animate-pulse rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
        <div className="h-20 animate-pulse rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
        <div className="h-20 animate-pulse rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
      </div>

      <div className="space-y-3">
        <div className="h-4 w-44 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        <div className="h-8 w-72 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <div className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-4">
          <div className="h-3 w-40 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-4 h-56 animate-pulse rounded-lg bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
        </div>
        <div className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-4">
          <div className="h-3 w-32 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-4 space-y-2">
            <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
          </div>
        </div>
      </div>
    </section>
  );
}
