import { redirect } from "next/navigation";

type ProjectChatPageProps = {
  params: Promise<{ projectId: string }>;
};

export default async function ProjectChatPage({ params }: ProjectChatPageProps) {
  const { projectId } = await params;
  redirect(`/projects/${projectId}/graphs/playground`);
}
