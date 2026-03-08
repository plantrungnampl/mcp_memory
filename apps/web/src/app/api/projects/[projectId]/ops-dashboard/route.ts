import { NextResponse } from "next/server";

import { getProjectOpsDashboard } from "@/app/projects/_lib/ops-dashboard";
import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { parseControlPlaneError } from "@/lib/api/control-plane-error";

export async function GET(
  _request: Request,
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const user = await getAuthenticatedProjectUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const payload = await getProjectOpsDashboard(user, projectId);
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
