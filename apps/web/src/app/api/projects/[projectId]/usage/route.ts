import { NextResponse } from "next/server";

import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { getUsage } from "@/lib/api/control-plane";
import { parseControlPlaneError } from "@/lib/api/control-plane-error";

function normalizePeriod(value: string | null): "daily" | "monthly" {
  return value === "daily" ? "daily" : "monthly";
}

export async function GET(
  request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const user = await getAuthenticatedProjectUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const url = new URL(request.url);
  const period = normalizePeriod(url.searchParams.get("period"));

  try {
    const usage = await getUsage(user, projectId, period);
    return NextResponse.json({ usage }, { status: 200 });
  } catch (error) {
    const parsed = parseControlPlaneError(error);
    return NextResponse.json(
      {
        error: parsed.message,
        detail: parsed.detail,
        request_id: parsed.requestId,
        upstream_status: parsed.status,
      },
      { status: parsed.status },
    );
  }
}
