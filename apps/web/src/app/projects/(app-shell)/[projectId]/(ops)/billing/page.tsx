import { redirect } from "next/navigation";

type ProjectBillingPageProps = {
  params: Promise<{ projectId: string }>;
};

export default async function ProjectBillingPage({ params }: ProjectBillingPageProps) {
  const { projectId } = await params;
  redirect(`/projects/${projectId}/graphs/playground`);
}
