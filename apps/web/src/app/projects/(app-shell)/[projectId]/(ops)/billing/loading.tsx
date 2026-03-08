export default function Loading() {
  return (
    <section
      aria-busy="true"
      aria-live="polite"
      className="mx-auto max-w-[1240px] space-y-5"
      role="status"
    >
      <span className="sr-only">Loading billing content</span>

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--vr-border)] pb-4">
        <div className="space-y-2">
          <div className="h-3 w-24 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="h-8 w-32 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        </div>
        <div className="h-9 w-32 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
      </div>

      <article className="rounded-xl border border-[var(--vr-accent)]/30 bg-[#13091F] px-6 py-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-3">
            <div className="h-8 w-40 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
            <div className="h-10 w-36 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
            <div className="h-4 w-72 max-w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          </div>
          <div className="w-full max-w-[320px] space-y-3">
            <div className="h-3 w-40 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
            <div className="space-y-2">
              <div className="h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
              <div className="h-2 w-full animate-pulse rounded-full bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
              <div className="h-3 w-56 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
            </div>
            <div className="h-8 w-40 animate-pulse rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
          </div>
        </div>
      </article>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="h-4 w-32 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
            <div className="h-8 w-28 animate-pulse rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
          </div>
          <div className="overflow-x-auto rounded-lg border border-[var(--vr-border)]">
            <div className="h-10 animate-pulse bg-[var(--vr-bg-input)] motion-reduce:animate-none" />
            <div className="space-y-2 p-4">
              <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
              <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
              <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            </div>
          </div>
        </article>

        <div className="space-y-4">
          <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
            <div className="mb-4 flex items-center justify-between gap-3">
              <div className="h-4 w-32 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
              <div className="h-3 w-14 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
            </div>
            <div className="h-20 animate-pulse rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
          </article>

          <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
            <div className="h-4 w-28 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
            <div className="mt-4 space-y-3">
              <div className="h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
              <div className="h-px bg-[var(--vr-border)]" />
              <div className="h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
              <div className="h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
            </div>
          </article>
        </div>
      </div>
    </section>
  );
}
