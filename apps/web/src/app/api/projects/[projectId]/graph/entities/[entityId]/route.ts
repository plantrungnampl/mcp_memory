import { NextResponse } from "next/server";

import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { getProjectGraphEntityDetail } from "@/lib/api/control-plane";
import { parseControlPlaneError } from "@/lib/api/control-plane-error";

function parsePositiveInt(value: string | null, fallback: number): number {
  if (!value) {
    return fallback;
  }
  const parsed = Number.parseInt(value, 10);
  if (Number.isNaN(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

export async function GET(
  request: Request,
  context: { params: Promise<{ projectId: string; entityId: string }> },
) {
  const { projectId, entityId } = await context.params;
  const user = await getAuthenticatedProjectUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const url = new URL(request.url);
  try {
    const payload = await getProjectGraphEntityDetail(user, projectId, entityId, {
      factLimit: parsePositiveInt(url.searchParams.get("fact_limit"), 120),
      episodeLimit: parsePositiveInt(url.searchParams.get("episode_limit"), 120),
      maxFactsScan: parsePositiveInt(url.searchParams.get("max_facts_scan"), 5000),
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
