import type {
  ProjectBillingOverview,
  UsageAnalyticsPayload,
  UsageRange,
  UsageSeries,
  UsageSummary,
} from "@/lib/api/types";
import { serverEnv } from "@/lib/server-env";

import {
  controlPlaneHeaders,
  fetchControlPlane,
  parseJson,
  type ControlPlaneUser,
} from "@/lib/api/control-plane-shared";

export async function getUsage(
  user: ControlPlaneUser,
  projectId: string,
  period: "daily" | "monthly",
): Promise<UsageSummary> {
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/usage?period=${period}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    usage: {
      period: "daily" | "monthly";
      vibe_tokens: number;
      in_tokens: number;
      out_tokens: number;
      event_count: number;
    };
  }>(response);

  return {
    period: payload.usage.period,
    vibeTokens: payload.usage.vibe_tokens,
    inTokens: payload.usage.in_tokens,
    outTokens: payload.usage.out_tokens,
    eventCount: payload.usage.event_count,
  };
}

export async function getUsageSeries(
  user: ControlPlaneUser,
  projectId: string,
  input: { windowDays: number; bucket: "day" },
): Promise<UsageSeries> {
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/usage/series?window_days=${input.windowDays}&bucket=${input.bucket}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    window_days: number;
    bucket: "day";
    series: Array<{
      bucket_start: string;
      vibe_tokens: number;
      in_tokens: number;
      out_tokens: number;
      event_count: number;
    }>;
  }>(response);
  return {
    windowDays: payload.window_days,
    bucket: payload.bucket,
    series: payload.series.map((entry) => ({
      bucketStart: entry.bucket_start,
      vibeTokens: entry.vibe_tokens,
      inTokens: entry.in_tokens,
      outTokens: entry.out_tokens,
      eventCount: entry.event_count,
    })),
  };
}

export async function getUsageAnalytics(
  user: ControlPlaneUser,
  projectId: string,
  range: UsageRange,
): Promise<UsageAnalyticsPayload> {
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/usage/analytics?range=${range}`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    range: UsageRange;
    window_days: number;
    date_range_label: string;
    summary: {
      api_calls: { value: number | null; change_pct: number | null };
      tokens_consumed: { value: number | null; change_pct: number | null };
      avg_response_time_ms: { value: number | null; change_pct: number | null };
      error_rate_pct: { value: number | null; change_pct: number | null };
    };
    trend: Array<{
      bucket_start: string;
      day_label: string;
      api_calls: number;
      vibe_tokens: number;
    }>;
    tool_distribution: Array<{
      tool: string;
      api_calls: number;
      share_pct: number;
    }>;
    token_breakdown: Array<{
      token_id: string;
      prefix: string;
      status: "active" | "grace" | "revoked";
      api_calls: number;
      vibe_tokens: number;
      avg_latency_ms: number | null;
      share_pct: number;
    }>;
    highlights: {
      peak_hour: string;
      most_active_token: string;
      busiest_day: string;
    };
  }>(response);

  return {
    range: payload.range,
    windowDays: payload.window_days,
    dateRangeLabel: payload.date_range_label,
    summary: {
      apiCalls: {
        value: payload.summary.api_calls.value,
        changePct: payload.summary.api_calls.change_pct,
      },
      tokensConsumed: {
        value: payload.summary.tokens_consumed.value,
        changePct: payload.summary.tokens_consumed.change_pct,
      },
      avgResponseTimeMs: {
        value: payload.summary.avg_response_time_ms.value,
        changePct: payload.summary.avg_response_time_ms.change_pct,
      },
      errorRatePct: {
        value: payload.summary.error_rate_pct.value,
        changePct: payload.summary.error_rate_pct.change_pct,
      },
    },
    trend: payload.trend.map((entry) => ({
      bucketStart: entry.bucket_start,
      dayLabel: entry.day_label,
      apiCalls: entry.api_calls,
      vibeTokens: entry.vibe_tokens,
    })),
    toolDistribution: payload.tool_distribution.map((entry) => ({
      tool: entry.tool,
      apiCalls: entry.api_calls,
      sharePct: entry.share_pct,
    })),
    tokenBreakdown: payload.token_breakdown.map((entry) => ({
      tokenId: entry.token_id,
      prefix: entry.prefix,
      status: entry.status,
      apiCalls: entry.api_calls,
      vibeTokens: entry.vibe_tokens,
      avgLatencyMs: entry.avg_latency_ms,
      sharePct: entry.share_pct,
    })),
    highlights: {
      peakHour: payload.highlights.peak_hour,
      mostActiveToken: payload.highlights.most_active_token,
      busiestDay: payload.highlights.busiest_day,
    },
  };
}

export async function getProjectBillingOverview(
  user: ControlPlaneUser,
  projectId: string,
): Promise<ProjectBillingOverview> {
  const response = await fetchControlPlane(
    `${serverEnv.controlPlaneApiBaseUrl}/api/control-plane/projects/${projectId}/billing/overview`,
    {
      cache: "no-store",
      headers: controlPlaneHeaders(user),
    },
  );
  const payload = await parseJson<{
    project_id: string;
    plan: ProjectBillingOverview["plan"];
    monthly_quota_vibe_tokens: number | null;
    current_month_vibe_tokens: number;
    current_month_events: number;
    remaining_vibe_tokens: number | null;
    utilization_pct: number | null;
    reset_at: string;
    last_7d_vibe_tokens: number;
    projected_month_vibe_tokens: number;
    plan_monthly_price_cents: number;
    renews_at: string;
    invoices: Array<{
      invoice_id: string;
      invoice_date: string;
      description: string;
      amount_cents: number;
      currency: string;
      status: ProjectBillingOverview["invoices"][number]["status"];
      pdf_url: string | null;
    }>;
    payment_method: {
      payment_method_id: string;
      brand: string;
      last4: string;
      exp_month: number;
      exp_year: number;
      is_default: boolean;
    } | null;
    billing_contact: {
      email: string | null;
      tax_id: string | null;
    };
  }>(response);

  return {
    projectId: payload.project_id,
    plan: payload.plan,
    monthlyQuotaVibeTokens: payload.monthly_quota_vibe_tokens,
    currentMonthVibeTokens: payload.current_month_vibe_tokens,
    currentMonthEvents: payload.current_month_events,
    remainingVibeTokens: payload.remaining_vibe_tokens,
    utilizationPct: payload.utilization_pct,
    resetAt: payload.reset_at,
    last7dVibeTokens: payload.last_7d_vibe_tokens,
    projectedMonthVibeTokens: payload.projected_month_vibe_tokens,
    planMonthlyPriceCents: payload.plan_monthly_price_cents,
    renewsAt: payload.renews_at,
    invoices: payload.invoices.map((invoice) => ({
      invoiceId: invoice.invoice_id,
      invoiceDate: invoice.invoice_date,
      description: invoice.description,
      amountCents: invoice.amount_cents,
      currency: invoice.currency,
      status: invoice.status,
      pdfUrl: invoice.pdf_url,
    })),
    paymentMethod: payload.payment_method
      ? {
          paymentMethodId: payload.payment_method.payment_method_id,
          brand: payload.payment_method.brand,
          last4: payload.payment_method.last4,
          expMonth: payload.payment_method.exp_month,
          expYear: payload.payment_method.exp_year,
          isDefault: payload.payment_method.is_default,
        }
      : null,
    billingContact: {
      email: payload.billing_contact.email,
      taxId: payload.billing_contact.tax_id,
    },
  };
}
