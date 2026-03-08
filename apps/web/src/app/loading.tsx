export default function Loading() {
  return (
    <div
      aria-busy="true"
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-0 z-[100]"
      role="status"
    >
      <span className="sr-only">Loading page</span>
      <div className="h-[2px] w-full bg-black/8">
        <div className="h-full w-full animate-pulse bg-gradient-to-r from-[#7a2dbe]/70 via-[#a855f7]/70 to-[#7a2dbe]/70 motion-reduce:animate-none" />
      </div>
    </div>
  );
}
