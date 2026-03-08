export default function Loading() {
  return (
    <section aria-busy="true" aria-live="polite" className="mx-auto max-w-[1240px] space-y-5" role="status">
      <span className="sr-only">Loading usage content</span>

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--vr-border)] pb-4">
        <div className="space-y-2">
          <div className="h-3 w-40 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="h-8 w-52 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        </div>
        <div className="h-9 w-28 animate-pulse rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 rounded-[10px] border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-1">
            <div className="h-7 w-10 animate-pulse rounded-[7px] bg-[var(--vr-divider)] motion-reduce:animate-none" />
            <div className="h-7 w-12 animate-pulse rounded-[7px] bg-[var(--vr-divider)] motion-reduce:animate-none" />
            <div className="h-7 w-12 animate-pulse rounded-[7px] bg-[var(--vr-divider)] motion-reduce:animate-none" />
            <div className="h-7 w-16 animate-pulse rounded-[7px] bg-[var(--vr-divider)] motion-reduce:animate-none" />
          </div>
          <div className="h-8 w-44 animate-pulse rounded-md border border-[var(--vr-divider)] bg-[var(--vr-bg-card)] motion-reduce:animate-none" />
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article className="h-[122px] rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="h-3 w-28 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-4 h-9 w-24 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-3 h-3 w-24 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        </article>
        <article className="h-[122px] rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="h-3 w-32 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-4 h-9 w-24 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-3 h-3 w-28 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        </article>
        <article className="h-[122px] rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="h-3 w-32 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-4 h-9 w-24 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-3 h-3 w-28 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        </article>
        <article className="h-[122px] rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-5">
          <div className="h-3 w-20 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-4 h-9 w-24 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-3 h-3 w-28 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        </article>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
          <div className="flex items-center justify-between gap-3">
            <div className="h-4 w-44 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
            <div className="h-3 w-24 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          </div>
          <div className="mt-4 h-[190px] animate-pulse rounded-lg bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
          <div className="mt-3 h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        </article>

        <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
          <div className="h-4 w-32 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-2 h-3 w-44 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <div className="h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
              <div className="h-1.5 w-full animate-pulse rounded-full bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            </div>
            <div className="space-y-2">
              <div className="h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
              <div className="h-1.5 w-full animate-pulse rounded-full bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            </div>
            <div className="h-px bg-[var(--vr-border)]" />
            <div className="space-y-2">
              <div className="h-3 w-28 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
              <div className="h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
              <div className="h-3 w-full animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
              <div className="h-1.5 w-full animate-pulse rounded-full bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            </div>
          </div>
        </article>
      </div>

      <article className="rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="h-4 w-40 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
          <div className="h-3 w-20 animate-pulse rounded-full bg-[var(--vr-divider)] motion-reduce:animate-none" />
        </div>
        <div className="overflow-x-auto rounded-lg border border-[var(--vr-border)]">
          <div className="h-10 animate-pulse rounded-t-lg bg-[var(--vr-bg-input)] motion-reduce:animate-none" />
          <div className="space-y-2 p-4">
            <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
            <div className="h-10 animate-pulse rounded-md bg-[var(--vr-bg-elevated)] motion-reduce:animate-none" />
          </div>
        </div>
      </article>
    </section>
  );
}
