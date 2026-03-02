import Link from "next/link";
import { BrainCircuit } from "lucide-react";

import { footerLinks } from "./landing-data";

export function LandingFooter() {
  return (
    <footer className="border-t border-white/5 bg-[#0a080c] py-12">
      <div className="mx-auto flex w-full max-w-7xl flex-col items-center justify-between gap-8 px-6 md:flex-row">
        <div className="flex items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-lg border border-[#7a2dbe]/30 bg-[#7a2dbe]/20">
            <BrainCircuit className="size-4.5 text-[#00f5ff]" />
          </div>
          <span className="text-lg font-bold tracking-tight text-slate-100">VibeRecall</span>
        </div>

        <div className="flex items-center gap-8 text-sm text-slate-500">
          {footerLinks.map((item) => (
            <Link key={item} href="#" className="transition-colors hover:text-[#00f5ff]">
              {item}
            </Link>
          ))}
        </div>

        <div className="flex flex-col items-end gap-1">
          <span className="font-mono text-sm text-slate-400">viberecall.ai</span>
          <span className="text-xs text-slate-600">© 2026 VibeRecall PRO. All rights reserved.</span>
        </div>
      </div>
    </footer>
  );
}
