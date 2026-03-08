import { NextResponse } from "next/server";

import {
  getAuthenticatedProjectUser,
  getProjectsBaseData,
} from "@/app/projects/_lib/projects-server";
import { parseControlPlaneError } from "@/lib/api/control-plane-error";

export async function GET() {
  const user = await getAuthenticatedProjectUser();
  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  try {
    const payload = await getProjectsBaseData(user);
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
