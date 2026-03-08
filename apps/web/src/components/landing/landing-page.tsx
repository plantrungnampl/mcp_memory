import { cn } from "@/lib/utils";

import { LandingFooter } from "./landing-footer";
import { LandingHeader } from "./landing-header";
import { LandingHero } from "./landing-hero";
import styles from "./landing-page.module.css";
import { LandingSections } from "./landing-sections";

export function LandingPage() {
  return (
    <div
      className={cn(
        styles.landingRoot,
        "min-h-screen text-slate-100",
      )}
    >
      <div className="relative flex min-h-screen w-full flex-col overflow-x-hidden">
        <LandingHeader />
        <main className="flex-1">
          <LandingHero />
          <LandingSections />
        </main>
        <LandingFooter />
      </div>
    </div>
  );
}
