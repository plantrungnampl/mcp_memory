export function KnowledgeGraphPanel() {
  return (
    <div className="relative h-[420px] w-full overflow-hidden rounded-[20px] border border-[#1f1f23] bg-[#111113]" aria-hidden="true">
      <div className="absolute left-1/2 top-1/2 size-[300px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,_rgba(122,45,190,0.28)_0%,_rgba(122,45,190,0)_72%)]" />

      <svg viewBox="0 0 100 100" className="absolute inset-0 z-10 size-full" role="presentation">
        <line x1="31" y1="24" x2="53" y2="18" stroke="rgba(168,85,247,0.35)" strokeWidth="0.4" />
        <line x1="53" y1="18" x2="58" y2="43" stroke="rgba(34,197,94,0.35)" strokeWidth="0.4" />
        <line x1="58" y1="43" x2="31" y2="66" stroke="rgba(0,245,255,0.35)" strokeWidth="0.4" />
        <line x1="31" y1="66" x2="66" y2="76" stroke="rgba(168,85,247,0.35)" strokeWidth="0.4" />
      </svg>

      <div className="absolute left-[18%] top-[18%] z-20 rounded-full border border-[#a855f7] bg-[#7a2dbe]/20 px-3 py-2 text-xs font-medium text-[#c084fc]">
        auth.ts
      </div>
      <div className="absolute left-[58%] top-[12%] z-20 rounded-full border border-[#22c55e] bg-[#22c55e]/15 px-3 py-2 text-xs font-medium text-[#22c55e]">
        GraphQL API
      </div>
      <div className="absolute left-[45%] top-[44%] z-20 rounded-full border border-[#00f5ff] bg-[#00f5ff]/15 px-3 py-2 text-xs font-medium text-[#00f5ff]">
        PR #247
      </div>
      <div className="absolute left-[14%] top-[64%] z-20 rounded-full border border-[#a855f7] bg-[#7a2dbe]/20 px-3 py-2 text-xs font-medium text-[#c084fc]">
        token refresh
      </div>
      <div className="absolute left-[64%] top-[75%] z-20 rounded-full border border-[#eab308] bg-[#eab308]/14 px-3 py-2 text-xs font-medium text-[#eab308]">
        migration
      </div>

      <p className="absolute bottom-6 left-1/2 z-20 -translate-x-1/2 text-[11px] text-[#6b6b70]">Dec 15 — Dec 22, 2025</p>
    </div>
  );
}
