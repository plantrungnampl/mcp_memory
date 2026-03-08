import { NextResponse } from "next/server";

import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { getProjectTimeline } from "@/lib/api/control-plane";
import { parseControlPlaneError } from "@/lib/api/control-plane-error";

function parseNonNegativeInt(value: string | null, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed < 0) {
    return fallback;
  }
  return parsed;
}

function parsePositiveInt(value: string | null, fallback: number): number {
  const parsed = parseNonNegativeInt(value, fallback);
  return parsed > 0 ? parsed : fallback;
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
  try {
    const payload = await getProjectTimeline(user, projectId, {
      limit: parsePositiveInt(url.searchParams.get("limit"), 50),
      offset: parseNonNegativeInt(url.searchParams.get("offset"), 0),
      fromTime: url.searchParams.get("from_time"),
      toTime: url.searchParams.get("to_time"),
    });
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
