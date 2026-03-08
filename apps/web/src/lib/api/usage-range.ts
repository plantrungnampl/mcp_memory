import type { UsageRange } from "@/lib/api/types";

export const USAGE_RANGE_OPTIONS: UsageRange[] = ["7d", "30d", "90d", "all"];

export function normalizeUsageRange(value: string | string[] | null | undefined): UsageRange {
  if (typeof value !== "string") {
    return "7d";
  }
  if (USAGE_RANGE_OPTIONS.includes(value as UsageRange)) {
    return value as UsageRange;
  }
  return "7d";
}
