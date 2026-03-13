import type { Metadata } from "next";

import { LoginScreen } from "@/components/login/login-screen";
import { publicEnv } from "@/lib/env";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to the VibeRecall control plane to create projects, mint MCP tokens, and inspect usage.",
  robots: {
    index: false,
    follow: false,
    googleBot: {
      index: false,
      follow: false,
      noimageindex: true,
      "max-image-preview": "none",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
};

export default function LoginPage() {
  return (
    <LoginScreen
      appUrl={publicEnv.appUrl}
      hasSupabase={publicEnv.hasSupabase}
      marketingUrl={publicEnv.marketingUrl}
    />
  );
}
