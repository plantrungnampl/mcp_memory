import { LoginScreen } from "@/components/login/login-screen";
import { publicEnv } from "@/lib/env";

export default function LoginPage() {
  return <LoginScreen appUrl={publicEnv.appUrl} hasSupabase={publicEnv.hasSupabase} />;
}
