import Link from "next/link";

import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";
import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getProjectApiLogs } from "@/lib/api/control-plane";

type ApiLogsPageProps = {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ cursor?: string }>;
};

function formatUtc(value: string | null): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });
}

export default async function ProjectApiLogsPage({ params, searchParams }: ApiLogsPageProps) {
  const { projectId } = await params;
  const query = await searchParams;
  const user = await getAuthenticatedProjectUser();

  if (!user) {
    return <AuthRequiredCard />;
  }

  const cursor = query.cursor ? Number(query.cursor) : null;
  const logsPage = await getProjectApiLogs(user, projectId, {
    limit: 50,
    cursor: Number.isNaN(cursor ?? Number.NaN) ? null : cursor,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight">API Logs</h1>
        <p className="text-sm text-slate-400">
          Recent control-plane audit records with cursor-based pagination.
        </p>
      </div>

      <Card className="border-[#7a2dbe]/30 bg-[#120e1d]/75 text-slate-100">
        <CardHeader>
          <CardDescription className="text-slate-400">Audit logs</CardDescription>
          <CardTitle>{logsPage.logs.length} rows</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="text-[11px] uppercase tracking-[0.14em] text-slate-400">
                <tr>
                  <th className="px-3 py-2">Time</th>
                  <th className="px-3 py-2">Action</th>
                  <th className="px-3 py-2">Status</th>
                  <th className="px-3 py-2">Tool</th>
                  <th className="px-3 py-2">Request</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#7a2dbe]/15">
                {logsPage.logs.map((log) => (
                  <tr key={log.id}>
                    <td className="px-3 py-3 text-xs text-slate-300">{formatUtc(log.createdAt)}</td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-200">{log.action}</td>
                    <td className="px-3 py-3 uppercase text-slate-300">{log.status}</td>
                    <td className="px-3 py-3 text-slate-300">{log.toolName ?? "-"}</td>
                    <td className="px-3 py-3 font-mono text-xs text-slate-500">{log.requestId ?? "-"}</td>
                  </tr>
                ))}
                {logsPage.logs.length === 0 ? (
                  <tr>
                    <td className="px-3 py-8 text-center text-slate-400" colSpan={5}>
                      No logs for this project yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          {logsPage.nextCursor ? (
            <div className="mt-4">
              <Button asChild variant="outline">
                <Link href={`/projects/${projectId}/api-logs?cursor=${logsPage.nextCursor}`}>Load more</Link>
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
