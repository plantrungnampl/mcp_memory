import "server-only";

import { getServerSupabaseClient } from "@/lib/supabase/server";

export type AuthenticatedControlPlaneUser = {
  email: string | null;
  id: string;
};

export async function getAuthenticatedControlPlaneUser(): Promise<AuthenticatedControlPlaneUser | null> {
  const supabase = await getServerSupabaseClient();
  const auth = supabase ? await supabase.auth.getUser() : { data: { user: null } };
  const authUser = auth.data.user;

  if (!authUser) {
    return null;
  }

  return {
    email: authUser.email ?? null,
    id: authUser.id,
  };
}

export async function requireAuthenticatedControlPlaneUser(): Promise<AuthenticatedControlPlaneUser> {
  const user = await getAuthenticatedControlPlaneUser();
  if (!user) {
    throw new Error("Authentication required.");
  }
  return user;
}
