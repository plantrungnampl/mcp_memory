import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getUsage, getUsageSeries } from "@/lib/api/control-plane";
import type { UsageSeries } from "@/lib/api/types";

type UsagePageProps = {
  params: Promise<{ projectId: string }>;
};

function chartBars(series: UsageSeries | null): Array<{ dayLabel: string; vibeTokens: number; height: number }> {
  const source = series?.series ?? [];
  if (source.length === 0) {
    return [];
  }
  const maxValue = Math.max(1, ...source.map((entry) => entry.vibeTokens));
  return source.map((entry) => {
    const date = new Date(entry.bucketStart);
    return {
      dayLabel: Number.isNaN(date.getTime())
        ? entry.bucketStart
        : date.toLocaleDateString("en-US", { month: "short", day: "2-digit" }),
      vibeTokens: entry.vibeTokens,
      height: Math.max(8, Math.round((entry.vibeTokens / maxValue) * 100)),
    };
  });
}

export default async function ProjectUsagePage({ params }: UsagePageProps) {
  const { projectId } = await params;
  const user = await getAuthenticatedProjectUser();

  if (!user) {
    return <AuthRequiredCard />;
  }

  const [usageDaily, usageMonthly, usageSeries] = await Promise.all([
    getUsage(user, projectId, "daily"),
    getUsage(user, projectId, "monthly"),
    getUsageSeries(user, projectId, { windowDays: 30, bucket: "day" }),
  ]);
  const bars = chartBars(usageSeries);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight">Usage Analytics</h1>
        <p className="text-sm text-slate-400">
          Monitor daily and monthly token consumption with 30-day trend visibility.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/75 text-slate-100">
          <CardHeader>
            <CardDescription className="text-slate-400">24h Usage</CardDescription>
            <CardTitle>{usageDaily.vibeTokens.toLocaleString()} VT</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-300">
            {usageDaily.eventCount.toLocaleString()} events · in {usageDaily.inTokens.toLocaleString()} · out{" "}
            {usageDaily.outTokens.toLocaleString()}
          </CardContent>
        </Card>

        <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/75 text-slate-100">
          <CardHeader>
            <CardDescription className="text-slate-400">30d Usage</CardDescription>
            <CardTitle>{usageMonthly.vibeTokens.toLocaleString()} VT</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-300">
            {usageMonthly.eventCount.toLocaleString()} events · in {usageMonthly.inTokens.toLocaleString()} · out{" "}
            {usageMonthly.outTokens.toLocaleString()}
          </CardContent>
        </Card>
      </div>

      <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/75 text-slate-100">
        <CardHeader>
          <CardDescription className="text-slate-400">Last {usageSeries.windowDays} days</CardDescription>
          <CardTitle>VibeTokens trend</CardTitle>
        </CardHeader>
        <CardContent>
          {bars.length > 0 ? (
            <>
              <div className="flex h-56 items-end gap-1">
                {bars.map((bar, index) => (
                  <div
                    className={`w-full rounded-t-sm ${index === bars.length - 1 ? "bg-[#7a2dbe] shadow-[0_0_18px_rgba(122,45,190,0.5)]" : "bg-[#7a2dbe]/35"}`}
                    key={`${bar.dayLabel}-${index}`}
                    style={{ height: `${bar.height}%` }}
                    title={`${bar.dayLabel}: ${bar.vibeTokens.toLocaleString()} VT`}
                  />
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between text-[10px] uppercase tracking-[0.14em] text-slate-400">
                <span>{bars[0]?.dayLabel ?? "-"}</span>
                <span>{bars[Math.floor(bars.length / 2)]?.dayLabel ?? "-"}</span>
                <span>{bars[bars.length - 1]?.dayLabel ?? "-"}</span>
              </div>
            </>
          ) : (
            <div className="flex h-40 items-center justify-center rounded-md border border-dashed border-[#7a2dbe]/30 text-sm text-slate-400">
              No usage events yet
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
