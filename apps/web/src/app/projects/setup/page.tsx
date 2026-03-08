import { AuthRequiredCard } from "@/components/projects/auth-required-card";
import { getAuthenticatedProjectUser } from "@/app/projects/_lib/projects-server";

export default async function ProjectsSetupPage() {
  const user = await getAuthenticatedProjectUser();
  if (!user) {
    return <AuthRequiredCard />;
  }

  return (
    <main className="min-h-screen bg-[var(--vr-bg-root)] px-4 py-8 md:px-8">
      <div className="mx-auto max-w-3xl rounded-xl border border-[var(--vr-border)] bg-[var(--vr-bg-card)] p-8">
        <p className="text-xs uppercase tracking-[0.12em] text-[var(--vr-text-dim)]">Projects</p>
        <h1 className="mt-2 text-2xl font-semibold text-[var(--vr-text-strong)]">Setup Wizard</h1>
        <p className="mt-3 text-sm text-[var(--vr-text-main)]">
          No project is available yet. Continue with your Setup Wizard flow to create the first project.
        </p>
      </div>
    </main>
  );
}
