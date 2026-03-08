import { NextResponse } from "next/server";

import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { getUsageAnalytics } from "@/lib/api/control-plane";
import { parseControlPlaneError } from "@/lib/api/control-plane-error";
import { normalizeUsageRange } from "@/lib/api/usage-range";

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
  const range = normalizeUsageRange(url.searchParams.get("range"));

  try {
    const analytics = await getUsageAnalytics(user, projectId, range);
    return NextResponse.json(analytics, { status: 200 });
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
