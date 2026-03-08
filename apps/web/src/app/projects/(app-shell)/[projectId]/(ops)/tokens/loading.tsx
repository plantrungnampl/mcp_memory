export default function Loading() {
  return (
    <section aria-busy="true" aria-live="polite" className="mx-auto max-w-[1240px] space-y-6" role="status">
      <span className="sr-only">Loading tokens dashboard</span>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="h-28 animate-pulse rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
        <div className="h-28 animate-pulse rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
        <div className="h-28 animate-pulse rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
        <div className="h-28 animate-pulse rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
          <div className="h-4 w-40 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-4 space-y-3">
            <div className="h-10 animate-pulse rounded-md border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-10 animate-pulse rounded-md border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-8 w-40 animate-pulse rounded-md border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
          </div>
        </article>

        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
          <div className="h-4 w-44 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-4 h-[140px] animate-pulse rounded-lg bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
          <div className="mt-3 h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        </article>
      </div>

      <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
        <div className="mb-4 h-4 w-40 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        <div className="overflow-x-auto rounded-lg border border-[var(--vr-border)]">
          <div className="h-10 animate-pulse bg-[var(--vr-bg-input)] motion-reduce:animate-none" />
          <div className="space-y-2 p-4">
            <div className="h-12 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-12 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-12 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
          </div>
        </div>
      </article>

      <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
        <div className="mb-4 h-4 w-36 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        <div className="overflow-x-auto rounded-lg border border-[var(--vr-border)]">
          <div className="h-10 animate-pulse bg-[var(--vr-bg-input)] motion-reduce:animate-none" />
          <div className="space-y-2 p-4">
            <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
          </div>
        </div>
      </article>

      <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
        <div className="mb-4 h-4 w-28 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        <div className="grid gap-4 xl:grid-cols-[1.1fr_1fr]">
          <div className="space-y-2 rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] p-4">
            <div className="h-8 w-28 animate-pulse rounded-md bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
            <div className="h-16 animate-pulse rounded-md bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
            <div className="h-16 animate-pulse rounded-md bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
          </div>
          <div className="space-y-2 rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] p-4">
            <div className="h-8 w-32 animate-pulse rounded-md bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
            <div className="h-20 animate-pulse rounded-md bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
            <div className="h-20 animate-pulse rounded-md bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
          </div>
        </div>
      </article>
    </section>
  );
}
