import { NextResponse, type NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/proxy";

function getWorkspaceRedirectPath(pathname: string): string | null {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length !== 3 || segments[0] !== "projects") {
    return null;
  }

  const [, projectId, section] = segments;
  if (section !== "chat" && section !== "billing") {
    return null;
  }

  return `/projects/${projectId}/graphs/playground`;
}

export async function proxy(request: NextRequest) {
  const redirectPath = getWorkspaceRedirectPath(request.nextUrl.pathname);
  if (redirectPath) {
    return NextResponse.redirect(new URL(redirectPath, request.url));
  }

  return updateSession(request);
}

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
