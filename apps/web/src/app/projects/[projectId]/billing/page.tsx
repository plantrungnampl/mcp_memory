import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getProjectBillingOverview } from "@/lib/api/control-plane";

type BillingPageProps = {
  params: Promise<{ projectId: string }>;
};

function formatUtc(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

export default async function ProjectBillingPage({ params }: BillingPageProps) {
  const { projectId } = await params;
  const user = await getAuthenticatedProjectUser();

  if (!user) {
    return <AuthRequiredCard />;
  }

  const billing = await getProjectBillingOverview(user, projectId);
  const pct = billing.utilizationPct ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight">Billing</h1>
        <p className="text-sm text-slate-400">
          Operational quota view based on plan limits and current month token burn.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/75 text-slate-100">
          <CardHeader>
            <CardDescription className="text-slate-400">Current month usage</CardDescription>
            <CardTitle>{billing.currentMonthVibeTokens.toLocaleString()} VT</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-300">
            {billing.currentMonthEvents.toLocaleString()} events
          </CardContent>
        </Card>

        <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/75 text-slate-100">
          <CardHeader>
            <CardDescription className="text-slate-400">Plan quota</CardDescription>
            <CardTitle>
              {billing.monthlyQuotaVibeTokens === null
                ? "Unlimited"
                : `${billing.monthlyQuotaVibeTokens.toLocaleString()} VT`}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm uppercase text-slate-300">{billing.plan} plan</CardContent>
        </Card>

        <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/75 text-slate-100">
          <CardHeader>
            <CardDescription className="text-slate-400">Remaining</CardDescription>
            <CardTitle>
              {billing.remainingVibeTokens === null
                ? "Unlimited"
                : `${billing.remainingVibeTokens.toLocaleString()} VT`}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-300">Resets at {formatUtc(billing.resetAt)}</CardContent>
        </Card>

        <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/75 text-slate-100">
          <CardHeader>
            <CardDescription className="text-slate-400">Projected month</CardDescription>
            <CardTitle>{billing.projectedMonthVibeTokens.toLocaleString()} VT</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-slate-300">
            Last 7d: {billing.last7dVibeTokens.toLocaleString()} VT
          </CardContent>
        </Card>
      </div>

      <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/75 text-slate-100">
        <CardHeader>
          <CardDescription className="text-slate-400">Utilization</CardDescription>
          <CardTitle>
            {billing.utilizationPct === null ? "N/A" : `${billing.utilizationPct.toFixed(2)}%`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-3 overflow-hidden rounded-full bg-slate-800/80">
            <div
              className="h-full rounded-full bg-[#7a2dbe]"
              style={{ width: `${Math.min(100, Math.max(0, pct))}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-slate-400">
            This tab shows operational usage metrics, not external payment invoices.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
