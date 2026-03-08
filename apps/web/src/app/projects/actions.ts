"use server";

import { randomUUID } from "node:crypto";

import { revalidatePath } from "next/cache";

import type {
  ExportActionState,
  MaintenanceActionState,
  ProjectActionState,
  TokenActionState,
} from "@/app/projects/action-types";
import {
  createProject,
  createProjectExport,
  migrateInlineToObject,
  mintToken,
  purgeProject,
  revokeToken,
  runProjectRetention,
  rotateToken,
  type ControlPlaneUser,
} from "@/lib/api/control-plane";
import { requireAuthenticatedControlPlaneUser } from "@/lib/auth/authenticated-user";

async function resolveUser(): Promise<ControlPlaneUser> {
  return requireAuthenticatedControlPlaneUser();
}

function actionNonce(): string {
  return Date.now().toString();
}

export async function createProjectAction(
  _prevState: ProjectActionState,
  formData: FormData,
): Promise<ProjectActionState> {
  const name = String(formData.get("name") ?? "").trim();
  if (name.length < 1) {
    return {
      ok: false,
      message: "Project name is required.",
      nonce: actionNonce(),
      projectId: null,
      connectionEndpoint: null,
      tokenPlaintext: null,
      tokenPrefix: null,
    };
  }

  try {
    const user = await resolveUser();
    const result = await createProject(user, {
      name,
      plan: "free",
    });
    revalidatePath("/projects");
    revalidatePath(`/projects/${result.project.id}`);
    return {
      ok: true,
      message: "Project created.",
      nonce: actionNonce(),
      projectId: result.project.id,
      connectionEndpoint: result.connection.endpoint,
      tokenPlaintext: result.token.plaintext,
      tokenPrefix: result.token.prefix,
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Failed to create project.",
      nonce: actionNonce(),
      projectId: null,
      connectionEndpoint: null,
      tokenPlaintext: null,
      tokenPrefix: null,
    };
  }
}

export async function mintTokenAction(
  _prevState: TokenActionState,
  formData: FormData,
): Promise<TokenActionState> {
  const projectId = String(formData.get("project_id") ?? "").trim();
  if (!projectId) {
    return {
      ok: false,
      message: "Project id is required.",
      nonce: actionNonce(),
      tokenPlaintext: null,
      tokenPrefix: null,
    };
  }

  try {
    const user = await resolveUser();
    const token = await mintToken(user, projectId);
    revalidatePath("/projects");
    revalidatePath(`/projects/${projectId}`);
    return {
      ok: true,
      message: "New token minted.",
      nonce: actionNonce(),
      tokenPlaintext: token.plaintext,
      tokenPrefix: token.prefix,
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Failed to mint token.",
      nonce: actionNonce(),
      tokenPlaintext: null,
      tokenPrefix: null,
    };
  }
}

export async function rotateTokenAction(
  _prevState: TokenActionState,
  formData: FormData,
): Promise<TokenActionState> {
  const projectId = String(formData.get("project_id") ?? "").trim();
  const tokenId = String(formData.get("token_id") ?? "").trim();
  if (!projectId || !tokenId) {
    return {
      ok: false,
      message: "Project id and token id are required.",
      nonce: actionNonce(),
      tokenPlaintext: null,
      tokenPrefix: null,
    };
  }

  try {
    const user = await resolveUser();
    const token = await rotateToken(user, projectId, tokenId);
    revalidatePath("/projects");
    revalidatePath(`/projects/${projectId}`);
    return {
      ok: true,
      message: "Token rotated. Previous token remains valid for grace window.",
      nonce: actionNonce(),
      tokenPlaintext: token.plaintext,
      tokenPrefix: token.prefix,
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Failed to rotate token.",
      nonce: actionNonce(),
      tokenPlaintext: null,
      tokenPrefix: null,
    };
  }
}

export async function revokeTokenAction(
  _prevState: TokenActionState,
  formData: FormData,
): Promise<TokenActionState> {
  const projectId = String(formData.get("project_id") ?? "").trim();
  const tokenId = String(formData.get("token_id") ?? "").trim();
  if (!projectId || !tokenId) {
    return {
      ok: false,
      message: "Project id and token id are required.",
      nonce: actionNonce(),
      tokenPlaintext: null,
      tokenPrefix: null,
    };
  }

  try {
    const user = await resolveUser();
    await revokeToken(user, projectId, tokenId);
    revalidatePath("/projects");
    revalidatePath(`/projects/${projectId}`);
    return {
      ok: true,
      message: "Token revoked.",
      nonce: actionNonce(),
      tokenPlaintext: null,
      tokenPrefix: null,
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Failed to revoke token.",
      nonce: actionNonce(),
      tokenPlaintext: null,
      tokenPrefix: null,
    };
  }
}

export async function createExportAction(
  _prevState: ExportActionState,
  formData: FormData,
): Promise<ExportActionState> {
  const projectId = String(formData.get("project_id") ?? "").trim();
  if (!projectId) {
    return {
      ok: false,
      message: "Project id is required.",
      nonce: actionNonce(),
      exportId: null,
      status: null,
    };
  }

  try {
    const user = await resolveUser();
    const exportRow = await createProjectExport(
      user,
      projectId,
      { format: "json_v1" },
      `exp-${projectId}-${randomUUID()}`,
    );
    revalidatePath("/projects");
    revalidatePath(`/projects/${projectId}`);
    return {
      ok: true,
      message: "Export queued.",
      nonce: actionNonce(),
      exportId: exportRow.exportId,
      status: exportRow.status,
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Failed to create export.",
      nonce: actionNonce(),
      exportId: null,
      status: null,
    };
  }
}

export async function runRetentionAction(
  _prevState: MaintenanceActionState,
  formData: FormData,
): Promise<MaintenanceActionState> {
  const projectId = String(formData.get("project_id") ?? "").trim();
  if (!projectId) {
    return {
      ok: false,
      message: "Project id is required.",
      nonce: actionNonce(),
      jobId: null,
      kind: null,
      status: null,
    };
  }

  try {
    const user = await resolveUser();
    const job = await runProjectRetention(user, projectId);
    revalidatePath("/projects");
    revalidatePath(`/projects/${projectId}`);
    return {
      ok: true,
      message: "Retention job queued.",
      nonce: actionNonce(),
      jobId: job.jobId,
      kind: job.kind,
      status: job.status,
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Failed to queue retention job.",
      nonce: actionNonce(),
      jobId: null,
      kind: null,
      status: null,
    };
  }
}

export async function purgeProjectAction(
  _prevState: MaintenanceActionState,
  formData: FormData,
): Promise<MaintenanceActionState> {
  const projectId = String(formData.get("project_id") ?? "").trim();
  const confirmProjectId = String(formData.get("confirm_project_id") ?? "").trim();
  if (!projectId) {
    return {
      ok: false,
      message: "Project id is required.",
      nonce: actionNonce(),
      jobId: null,
      kind: null,
      status: null,
    };
  }
  if (!confirmProjectId || confirmProjectId !== projectId) {
    return {
      ok: false,
      message: "Type the exact project id to confirm purge.",
      nonce: actionNonce(),
      jobId: null,
      kind: null,
      status: null,
    };
  }

  try {
    const user = await resolveUser();
    const job = await purgeProject(user, projectId, `purge-${projectId}-${randomUUID()}`);
    revalidatePath("/projects");
    revalidatePath(`/projects/${projectId}`);
    return {
      ok: true,
      message: "Purge job queued.",
      nonce: actionNonce(),
      jobId: job.jobId,
      kind: job.kind,
      status: job.status,
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : "Failed to queue purge job.",
      nonce: actionNonce(),
      jobId: null,
      kind: null,
      status: null,
    };
  }
}

export async function migrateInlineToObjectAction(
  _prevState: MaintenanceActionState,
  formData: FormData,
): Promise<MaintenanceActionState> {
  const projectId = String(formData.get("project_id") ?? "").trim();
  const force = formData.get("force") !== null;
  if (!projectId) {
    return {
      ok: false,
      message: "Project id is required.",
      nonce: actionNonce(),
      jobId: null,
      kind: null,
      status: null,
    };
  }

  try {
    const user = await resolveUser();
    const job = await migrateInlineToObject(
      user,
      projectId,
      { force },
      `migrate-${projectId}-${force ? "force" : "safe"}-${randomUUID()}`,
    );
    revalidatePath("/projects");
    revalidatePath(`/projects/${projectId}`);
    return {
      ok: true,
      message: force
        ? "Forced migrate-inline-to-object job queued."
        : "Migrate-inline-to-object job queued.",
      nonce: actionNonce(),
      jobId: job.jobId,
      kind: job.kind,
      status: job.status,
    };
  } catch (error) {
    return {
      ok: false,
      message:
        error instanceof Error
          ? error.message
          : "Failed to queue migrate-inline-to-object job.",
      nonce: actionNonce(),
      jobId: null,
      kind: null,
      status: null,
    };
  }
}
