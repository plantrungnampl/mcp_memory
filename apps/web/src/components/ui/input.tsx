import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "flex h-12 w-full rounded-full border border-black/10 bg-white px-4 py-3 text-sm text-stone-950 outline-none transition-colors placeholder:text-stone-400 focus-visible:border-stone-400",
        className,
      )}
      type={type}
      {...props}
    />
  );
}

export { Input };
