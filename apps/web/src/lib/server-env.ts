export const serverEnv = {
  controlPlaneApiBaseUrl:
    process.env.CONTROL_PLANE_API_BASE_URL ??
    process.env.NEXT_PUBLIC_MCP_BASE_URL ??
    "http://localhost:8010",
  controlPlaneInternalSecret:
    process.env.CONTROL_PLANE_INTERNAL_SECRET ?? "dev-control-plane-secret",
};
