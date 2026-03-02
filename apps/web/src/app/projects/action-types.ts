export type ProjectActionState = {
  ok: boolean;
  message: string | null;
  nonce: string | null;
  projectId: string | null;
  tokenPlaintext: string | null;
  tokenPrefix: string | null;
};

export const INITIAL_PROJECT_ACTION_STATE: ProjectActionState = {
  ok: false,
  message: null,
  nonce: null,
  projectId: null,
  tokenPlaintext: null,
  tokenPrefix: null,
};

export type TokenActionState = {
  ok: boolean;
  message: string | null;
  nonce: string | null;
  tokenPlaintext: string | null;
  tokenPrefix: string | null;
};

export const INITIAL_TOKEN_ACTION_STATE: TokenActionState = {
  ok: false,
  message: null,
  nonce: null,
  tokenPlaintext: null,
  tokenPrefix: null,
};

export type ExportActionState = {
  ok: boolean;
  message: string | null;
  nonce: string | null;
  exportId: string | null;
  status: "pending" | "processing" | "complete" | "failed" | null;
};

export const INITIAL_EXPORT_ACTION_STATE: ExportActionState = {
  ok: false,
  message: null,
  nonce: null,
  exportId: null,
  status: null,
};

export type MaintenanceActionState = {
  ok: boolean;
  message: string | null;
  nonce: string | null;
  jobId: string | null;
  kind: "retention" | "purge_project" | "migrate_inline_to_object" | null;
  status: "queued" | null;
};

export const INITIAL_MAINTENANCE_ACTION_STATE: MaintenanceActionState = {
  ok: false,
  message: null,
  nonce: null,
  jobId: null,
  kind: null,
  status: null,
};
