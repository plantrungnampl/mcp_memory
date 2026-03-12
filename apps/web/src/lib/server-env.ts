type ServerEnv = {
  controlPlaneApiBaseUrl: string;
  controlPlaneInternalSecret: string;
};

function requireServerEnv(env: NodeJS.ProcessEnv, name: string): string {
  const value = env[name]?.trim();
  if (!value) {
    throw new Error(`Missing required server environment variable: ${name}`);
  }
  return value;
}

export function resolveServerEnv(env: NodeJS.ProcessEnv = process.env): ServerEnv {
  return {
    controlPlaneApiBaseUrl: requireServerEnv(env, "CONTROL_PLANE_API_BASE_URL"),
    controlPlaneInternalSecret: requireServerEnv(env, "CONTROL_PLANE_INTERNAL_SECRET"),
  };
}

export const serverEnv = resolveServerEnv();
