import { NextResponse } from "next/server";

import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { parseControlPlaneError } from "@/lib/api/control-plane-error";
import { getProjectApiLogsAnalytics } from "@/lib/api/control-plane";
import { normalizeApiLogsSearchState } from "@/lib/api/api-logs-search";

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
  const filters = normalizeApiLogsSearchState({
    range: url.searchParams.get("range"),
    statusFilter: url.searchParams.get("status_filter"),
    tool: url.searchParams.get("tool"),
    query: url.searchParams.get("q"),
    cursor: url.searchParams.get("cursor"),
    limit: url.searchParams.get("limit"),
  });

  try {
    const payload = await getProjectApiLogsAnalytics(user, projectId, filters);
    return NextResponse.json(payload, { status: 200 });
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
