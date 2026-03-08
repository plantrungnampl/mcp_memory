function requireServerEnv(name: string): string {
  const value = process.env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required server environment variable: ${name}`);
  }
  return value;
}

export const serverEnv = {
  controlPlaneApiBaseUrl:
    process.env.CONTROL_PLANE_API_BASE_URL ??
    process.env.NEXT_PUBLIC_MCP_BASE_URL ??
    "http://localhost:8010",
  controlPlaneInternalSecret: requireServerEnv("CONTROL_PLANE_INTERNAL_SECRET"),
};
