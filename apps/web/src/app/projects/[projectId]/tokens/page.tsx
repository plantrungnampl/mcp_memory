import {
  createExportAction,
  migrateInlineToObjectAction,
  mintTokenAction,
  purgeProjectAction,
  revokeTokenAction,
  rotateTokenAction,
  runRetentionAction,
} from "@/app/projects/actions";
import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { TokenPanelPlaceholder } from "@/components/token-panel-placeholder";
import {
  getConnection,
  getProjectExports,
  getProjectTokens,
  getUsage,
} from "@/lib/api/control-plane";

type TokensPageProps = {
  params: Promise<{ projectId: string }>;
};

export default async function ProjectTokensPage({ params }: TokensPageProps) {
  const { projectId } = await params;
  const user = await getAuthenticatedProjectUser();

  if (!user) {
    return <AuthRequiredCard />;
  }

  const [tokens, connection, usageDaily, usageMonthly, exports] = await Promise.all([
    getProjectTokens(user, projectId),
    getConnection(user, projectId),
    getUsage(user, projectId, "daily"),
    getUsage(user, projectId, "monthly"),
    getProjectExports(user, projectId),
  ]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-black tracking-tight">VibeTokens</h1>
        <p className="text-sm text-slate-400">
          Manage project tokens, exports, and maintenance operations.
        </p>
      </div>

      <TokenPanelPlaceholder
        activeProjectId={projectId}
        connection={connection}
        createExportAction={createExportAction}
        exports={exports}
        migrateInlineToObjectAction={migrateInlineToObjectAction}
        mintTokenAction={mintTokenAction}
        purgeProjectAction={purgeProjectAction}
        revokeTokenAction={revokeTokenAction}
        rotateTokenAction={rotateTokenAction}
        runRetentionAction={runRetentionAction}
        tokens={tokens}
        usageDaily={usageDaily}
        usageMonthly={usageMonthly}
      />
    </div>
  );
}
