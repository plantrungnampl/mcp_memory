import { NextResponse } from "next/server";

import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { getProjectGraph } from "@/lib/api/control-plane";
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
  context: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await context.params;
  const user = await getAuthenticatedProjectUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const url = new URL(request.url);
  const q = url.searchParams.get("q");
  const entityTypesRaw = url.searchParams.get("entity_types");
  const entityTypes = entityTypesRaw
    ? entityTypesRaw
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item.length > 0)
    : [];
  const lastDaysParam = url.searchParams.get("last_days");
  const lastDays = lastDaysParam ? parsePositiveInt(lastDaysParam, 30) : null;

  try {
    const payload = await getProjectGraph(user, projectId, {
      query: q,
      entityTypes,
      lastDays,
      maxNodes: parsePositiveInt(url.searchParams.get("max_nodes"), 1500),
      maxEdges: parsePositiveInt(url.searchParams.get("max_edges"), 4000),
      maxFacts: parsePositiveInt(url.searchParams.get("max_facts"), 5000),
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
