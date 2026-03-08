import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { parseControlPlaneError } from "@/lib/api/control-plane-error";

type ControlPlaneErrorStateProps = {
  actionHref: string;
  actionLabel: string;
  error: unknown;
  title: string;
};

function toDetailText(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail;
  }
  return null;
}

export function ControlPlaneErrorState({
  actionHref,
  actionLabel,
  error,
  title,
}: ControlPlaneErrorStateProps) {
  const parsed = parseControlPlaneError(error);
  const detailText = toDetailText(parsed.detail);
  const isMissingAssertion = parsed.status === 401 && detailText === "Missing control-plane assertion";

  return (
    <Card className="border-[var(--vr-border)] bg-[var(--vr-bg-card)] text-[var(--vr-text-strong)]">
      <CardHeader>
        <CardDescription className="text-[var(--vr-text-main)]">Control-plane backend</CardDescription>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 text-sm text-[var(--vr-text-main)]">
        {isMissingAssertion ? (
          <>
            <p>Workspace session is out of sync with the control-plane.</p>
            <p>Refresh the page or sign in again to mint a fresh internal assertion.</p>
          </>
        ) : (
          <p>{detailText ?? parsed.message}</p>
        )}
        {parsed.requestId ? (
          <p className="font-mono text-xs text-[var(--vr-text-dim)]">Request ID: {parsed.requestId}</p>
        ) : null}
        <Button
          asChild
          className="border-[var(--vr-divider)] bg-[var(--vr-bg-card)] text-[var(--vr-text-strong)] hover:bg-[var(--vr-bg-elevated)]"
          variant="outline"
        >
          <Link href={actionHref}>{actionLabel}</Link>
        </Button>
      </CardContent>
    </Card>
  );
}
