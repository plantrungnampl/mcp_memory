import { NextResponse, type NextRequest } from "next/server";

import { publicEnv } from "@/lib/env";
import { updateSession } from "@/lib/supabase/proxy";

type RedirectDecision = {
  destination: string;
  statusCode: 307 | 308;
};

function normalizeHost(hostHeader: string | null): string {
  return (hostHeader || "").trim().toLowerCase();
}

function bareDomain(host: string): string {
  return host.startsWith("www.") ? host.slice(4) : host;
}

function isAppSurfacePath(pathname: string): boolean {
  return (
    pathname === "/login" ||
    pathname.startsWith("/login/") ||
    pathname === "/projects" ||
    pathname.startsWith("/projects/") ||
    pathname === "/auth" ||
    pathname.startsWith("/auth/")
  );
}

export function resolveHostRedirect(
  requestUrl: string,
  hostHeader: string | null,
  options: {
    marketingOrigin?: string;
    appOrigin?: string;
  } = {},
): RedirectDecision | null {
  const { marketingOrigin = publicEnv.marketingUrl, appOrigin = publicEnv.appUrl } = options;
  const url = new URL(requestUrl);
  const requestHost = normalizeHost(hostHeader || url.host);
  const marketingUrl = new URL(marketingOrigin);
  const appUrl = new URL(appOrigin);
  const marketingHost = normalizeHost(marketingUrl.host);
  const appHost = normalizeHost(appUrl.host);
  const rootHost = bareDomain(marketingHost);

  if (!marketingHost || !appHost || marketingHost === appHost) {
    return null;
  }

  if (requestHost && requestHost === rootHost && requestHost !== marketingHost) {
    url.protocol = marketingUrl.protocol;
    url.host = marketingHost;
    return {
      destination: url.toString(),
      statusCode: 308,
    };
  }

  if (requestHost && requestHost === marketingHost && isAppSurfacePath(url.pathname)) {
    url.protocol = appUrl.protocol;
    url.host = appHost;
    return {
      destination: url.toString(),
      statusCode: 308,
    };
  }

  if (requestHost && requestHost === appHost && url.pathname === "/") {
    url.protocol = appUrl.protocol;
    url.host = appHost;
    url.pathname = "/login";
    return {
      destination: url.toString(),
      statusCode: 307,
    };
  }

  return null;
}

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
  const hostRedirect = resolveHostRedirect(request.url, request.headers.get("host"));
  if (hostRedirect) {
    return NextResponse.redirect(hostRedirect.destination, hostRedirect.statusCode);
  }

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
