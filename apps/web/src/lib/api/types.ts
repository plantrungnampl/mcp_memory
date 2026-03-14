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

export type UsageRange = "7d" | "30d" | "90d" | "all";

export type UsageAnalyticsMetric = {
  value: number | null;
  changePct: number | null;
};

export type UsageAnalyticsSummary = {
  apiCalls: UsageAnalyticsMetric;
  tokensConsumed: UsageAnalyticsMetric;
  avgResponseTimeMs: UsageAnalyticsMetric;
  errorRatePct: UsageAnalyticsMetric;
};

export type UsageAnalyticsTrendPoint = {
  bucketStart: string;
  dayLabel: string;
  apiCalls: number;
  vibeTokens: number;
};

export type UsageAnalyticsToolDistributionItem = {
  tool: string;
  apiCalls: number;
  sharePct: number;
};

export type UsageAnalyticsTokenBreakdownRow = {
  tokenId: string;
  prefix: string;
  status: "active" | "grace" | "revoked";
  apiCalls: number;
  vibeTokens: number;
  avgLatencyMs: number | null;
  sharePct: number;
};

export type UsageAnalyticsHighlights = {
  peakHour: string;
  mostActiveToken: string;
  busiestDay: string;
};

export type UsageAnalyticsPayload = {
  range: UsageRange;
  windowDays: number;
  dateRangeLabel: string;
  summary: UsageAnalyticsSummary;
  trend: UsageAnalyticsTrendPoint[];
  toolDistribution: UsageAnalyticsToolDistributionItem[];
  tokenBreakdown: UsageAnalyticsTokenBreakdownRow[];
  highlights: UsageAnalyticsHighlights;
};

export type GraphEntityType = string;
export type GraphViewMode = "concepts" | "code";
export type GraphEmptyReason = "none" | "concepts_unavailable" | "no_ready_index" | "no_graph_data";
export type ProjectIndexStatus = "missing" | "queued" | "running" | "stalled" | "ready" | "failed";
export type ProjectIndexRecommendedAction = "start_index" | "wait" | "check_workers" | "retry" | "none";

export type ProjectIndexSummary = {
  status: ProjectIndexStatus;
  currentRunId: string | null;
  latestReadyAt: string | null;
  queuedAt: string | null;
  startedAt: string | null;
  completedAt: string | null;
  ageSeconds: number | null;
  errorCode: string | null;
  errorMessage: string | null;
  recommendedAction: ProjectIndexRecommendedAction;
};

export type ProjectGraphHoverItem = {
  text: string;
  referenceTime: string | null;
};

export type ProjectGraphNode = {
  entityId: string;
  type: GraphEntityType;
  name: string;
  factCount: number;
  episodeCount: number;
  referenceTime: string | null;
  hoverText: ProjectGraphHoverItem[];
};

export type ProjectGraphEdge = {
  edgeId: string;
  type: string;
  sourceEntityId: string;
  targetEntityId: string;
  weight: number;
  episodeCount: number;
  label: string;
};

export type ProjectGraphPayload = {
  generatedAt: string;
  mode: GraphViewMode;
  emptyReason: GraphEmptyReason;
  indexSummary: ProjectIndexSummary | null;
  availableModes: GraphViewMode[];
  nodePrimaryLabel: string;
  nodeSecondaryLabel: string;
  edgeSupportLabel: string;
  entityCount: number;
  relationshipCount: number;
  truncated: boolean;
  nodes: ProjectGraphNode[];
  edges: ProjectGraphEdge[];
};

export type ProjectGraphEntityFact = {
  factId: string;
  text: string;
  validAt: string | null;
  invalidAt: string | null;
  ingestedAt: string | null;
  provenance: {
    episodeIds: string[];
    referenceTime: string | null;
    ingestedAt: string | null;
  };
};

export type ProjectTimelineEpisode = {
  episodeId: string;
  referenceTime: string | null;
  ingestedAt: string | null;
  summary: string | null;
  metadata: Record<string, unknown>;
};

export type ProjectGraphEntityDetail = {
  mode: GraphViewMode;
  entity: {
    entityId: string;
    type: GraphEntityType;
    name: string;
    factCount: number;
    episodeCount: number;
    filePaths?: string[];
    language?: string | null;
    kind?: string | null;
  };
  facts: ProjectGraphEntityFact[];
  provenance: ProjectTimelineEpisode[];
  relatedEntities: Array<{
    entityId: string;
    type: GraphEntityType;
    name: string;
    relationType: string;
    supportCount: number;
  }>;
  citations: Array<{
    citationId: string;
    sourceType: string;
    entityId: string;
    filePath: string | null;
    lineStart: number | null;
    lineEnd: number | null;
    snippet: string | null;
  }>;
  symbols: Array<{
    entityId: string;
    name: string;
    kind: string | null;
    filePath: string | null;
    lineStart: number | null;
    lineEnd: number | null;
    language: string | null;
  }>;
};

export type ProjectTimelinePayload = {
  rows: ProjectTimelineEpisode[];
  offset: number;
  limit: number;
  hasMore: boolean;
  nextOffset: number | null;
};

export type BillingInvoiceStatus = "paid" | "open" | "void" | "failed";

export type BillingInvoice = {
  invoiceId: string;
  invoiceDate: string;
  description: string;
  amountCents: number;
  currency: string;
  status: BillingInvoiceStatus;
  pdfUrl: string | null;
};

export type BillingPaymentMethod = {
  paymentMethodId: string;
  brand: string;
  last4: string;
  expMonth: number;
  expYear: number;
  isDefault: boolean;
};

export type BillingContact = {
  email: string | null;
  taxId: string | null;
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
  planMonthlyPriceCents: number;
  renewsAt: string;
  invoices: BillingInvoice[];
  paymentMethod: BillingPaymentMethod | null;
  billingContact: BillingContact;
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
  latencyMs?: number | null;
};

export type ProjectApiLogsPage = {
  logs: ProjectApiLogRow[];
  nextCursor: number | null;
};

export type ApiLogsRange = "24h" | "7d" | "30d" | "90d" | "all";

export type ApiLogsStatusFilter = "all" | "success" | "error";

export type ApiLogsMetric = {
  value: number | null;
  changePct: number | null;
};

export type ProjectApiLogsAnalyticsSummary = {
  totalRequests: ApiLogsMetric;
  successRatePct: ApiLogsMetric;
  errorCount: ApiLogsMetric;
  p95LatencyMs: ApiLogsMetric;
};

export type ProjectApiLogsAnalyticsRow = {
  id: number;
  time: string | null;
  tool: string | null;
  status: string | null;
  latencyMs: number | null;
  tokenPrefix: string | null;
  requestId: string | null;
  action: string | null;
};

export type ProjectApiLogsAnalyticsPagination = {
  totalRows: number;
  showingFrom: number;
  showingTo: number;
  nextCursor: string | null;
  prevCursor: string | null;
};

export type ProjectApiLogsAnalyticsPayload = {
  range: ApiLogsRange;
  filters: {
    statusFilter: ApiLogsStatusFilter;
    tool: string | null;
    query: string | null;
  };
  summary: ProjectApiLogsAnalyticsSummary;
  table: {
    rows: ProjectApiLogsAnalyticsRow[];
    toolOptions: string[];
    pagination: ProjectApiLogsAnalyticsPagination;
  };
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

export type ProjectsDirectoryPayload = {
  projects: ProjectSummary[];
  overviewRows: ProjectOverviewRow[];
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

export type ProjectOpsDashboardPayload = {
  generatedAt: string;
  tokens: ProjectToken[];
  connection: McpConnectionInfo | null;
  usageDaily: UsageSummary | null;
  usageMonthly: UsageSummary | null;
  usageSeries: UsageSeries | null;
  overviewRow: ProjectOverviewRow | null;
  indexSummary: ProjectIndexSummary | null;
  logs: ProjectApiLogRow[];
  exports: ProjectExport[];
};
