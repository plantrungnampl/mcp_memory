export type PlanName = "free" | "pro" | "team";

export type ProjectSummary = {
  id: string;
  name: string;
  plan: PlanName;
  createdAt: string;
};

export type TokenPreview = {
  tokenId: string;
  prefix: string;
  createdAt: string;
  lastUsedAt: string | null;
  revokedAt: string | null;
};

export type McpConnectionInfo = {
  endpoint: string;
  tokenPreview: string;
};

export type TokenStatus = "active" | "grace" | "revoked";

export type ProjectToken = {
  tokenId: string;
  prefix: string;
  createdAt: string;
  lastUsedAt: string | null;
  revokedAt: string | null;
  expiresAt: string | null;
  status: TokenStatus;
};

export type PlaintextTokenReveal = {
  tokenId: string;
  prefix: string;
  plaintext: string;
  createdAt: string;
  revokedAt: string | null;
  expiresAt: string | null;
  status: TokenStatus;
};

export type CreatedProjectResult = {
  project: ProjectSummary;
  connection: McpConnectionInfo;
  token: PlaintextTokenReveal;
};

export type UsageSummary = {
  period: "daily" | "monthly";
  vibeTokens: number;
  inTokens: number;
  outTokens: number;
  eventCount: number;
};

export type UsageSeriesBucket = {
  bucketStart: string;
  vibeTokens: number;
  inTokens: number;
  outTokens: number;
  eventCount: number;
};

export type UsageSeries = {
  bucket: "day";
  windowDays: number;
  series: UsageSeriesBucket[];
};

export type ProjectBillingOverview = {
  projectId: string;
  plan: PlanName;
  monthlyQuotaVibeTokens: number | null;
  currentMonthVibeTokens: number;
  currentMonthEvents: number;
  remainingVibeTokens: number | null;
  utilizationPct: number | null;
  resetAt: string;
  last7dVibeTokens: number;
  projectedMonthVibeTokens: number;
};

export type ProjectApiLogRow = {
  id: number;
  requestId: string | null;
  projectId: string | null;
  tokenId: string | null;
  toolName: string | null;
  action: string;
  argsHash: string | null;
  status: string;
  createdAt: string | null;
};

export type ProjectApiLogsPage = {
  logs: ProjectApiLogRow[];
  nextCursor: number | null;
};

export type ProjectOverviewTokenStatus = "active" | "grace" | "revoked" | "missing";
export type ProjectOverviewHealthStatus = "active" | "idle" | "error";

export type ProjectOverviewRow = {
  id: string;
  name: string;
  plan: PlanName;
  createdAt: string;
  lastActivityAt: string | null;
  vibeTokensWindow: number;
  tokenPreview: string | null;
  tokenStatus: ProjectOverviewTokenStatus;
  healthStatus: ProjectOverviewHealthStatus;
};

export type ExportStatus = "pending" | "processing" | "complete" | "failed";

export type ProjectExport = {
  exportId: string;
  projectId: string;
  status: ExportStatus;
  format: "json_v1";
  objectUrl: string | null;
  expiresAt: string | null;
  error: string | null;
  requestedBy: string | null;
  requestedAt: string;
  completedAt: string | null;
  jobId: string | null;
};

export type MaintenanceJobKind = "retention" | "purge_project" | "migrate_inline_to_object";

export type MaintenanceJobStatus = "queued";

export type MaintenanceJob = {
  jobId: string;
  kind: MaintenanceJobKind;
  status: MaintenanceJobStatus;
  retentionDays: number | null;
  force: boolean | null;
};
