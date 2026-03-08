import Link from "next/link";
import { Brain, Github, Mail, Twitter } from "lucide-react";

import { cn } from "@/lib/utils";

import { footerColumns } from "./landing-data";
import styles from "./landing-page.module.css";

export function LandingFooter() {
  return (
    <footer className="border-t border-[#1f1f23] bg-[#080810] px-6 py-[60px] md:px-[120px]">
      <div className="mx-auto w-full max-w-[1200px] space-y-10">
        <div className="flex flex-col justify-between gap-10 lg:flex-row">
          <div className="max-w-[300px] space-y-3">
            <div className="flex items-center gap-2.5">
              <div className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-[#7a2dbe] to-[#a855f7]">
                <Brain className="size-4.5 text-white" />
              </div>
              <span className={cn("text-[15px] font-semibold tracking-[0.14em] text-white", styles.fontMono)}>
                VIBERECALL
              </span>
            </div>
            <p className="whitespace-pre-line text-[13px] leading-[1.6] text-[#6b6b70]">
              {"Long-term memory for your coding agent.\nNative MCP. Bi-temporal. Secure."}
            </p>
          </div>

          <div className="flex flex-wrap gap-12 md:gap-20">
            {footerColumns.map((column) => (
              <div key={column.title} className="space-y-3.5">
                <p className="text-xs font-semibold tracking-[0.04em] text-[#adadb0]">{column.title}</p>
                <div className="space-y-3.5">
                  {column.links.map((item) => (
                    <Link
                      key={`${column.title}-${item}`}
                      href="#"
                      className={cn("block text-[13px] text-[#6b6b70] transition-colors hover:text-[#adadb0]", styles.footerLink)}
                    >
                      {item}
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="h-px w-full bg-[#1f1f23]" />

        <div className="flex flex-col items-start justify-between gap-5 md:flex-row md:items-center">
          <p className="text-xs text-[#4a4a4e]">© 2026 VibeRecall. All rights reserved.</p>
          <div className="flex items-center gap-4 text-[#6b6b70]">
            <Link href="#" aria-label="GitHub" className="transition-colors hover:text-[#adadb0]">
              <Github className="size-[18px]" />
            </Link>
            <Link href="#" aria-label="Twitter" className="transition-colors hover:text-[#adadb0]">
              <Twitter className="size-[18px]" />
            </Link>
            <Link href="#" aria-label="Email" className="transition-colors hover:text-[#adadb0]">
              <Mail className="size-[18px]" />
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
