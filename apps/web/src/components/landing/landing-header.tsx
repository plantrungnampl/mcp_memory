import { Brain } from "lucide-react";

import { cn } from "@/lib/utils";

import { LandingAuthControls } from "./landing-auth-controls";
import { navItems } from "./landing-data";
import styles from "./landing-page.module.css";

export function LandingHeader() {
  return (
    <header className={cn("border-b border-[#1f1f23]", styles.glassHeader)}>
      <div className="mx-auto flex h-[76px] w-full max-w-[1440px] items-center justify-between px-6 md:px-20">
        <div className="flex items-center gap-2.5">
          <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-[#7a2dbe] to-[#a855f7]">
            <Brain className="size-5 text-white" />
          </div>
          <span className={cn("text-[18px] font-semibold tracking-[0.16em] text-white", styles.fontMono)}>
            VIBERECALL
          </span>
        </div>

        <nav className="hidden items-center gap-8 md:flex">
          {navItems.map((item) => (
            <a
              key={item.label}
              href={item.href}
              className={cn("text-sm font-medium text-[#adadb0] transition-colors hover:text-white", styles.navLink)}
            >
              {item.label}
            </a>
          ))}
        </nav>

        <LandingAuthControls />
      </div>
    </header>
  );
}
