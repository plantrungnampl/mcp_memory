import "server-only";

import { createSignedControlPlaneAssertion } from "@/lib/auth/control-plane-assertion-core";
import { serverEnv } from "@/lib/server-env";

type ControlPlaneAssertionSubject = {
  id: string;
  email?: string | null;
};

export function createControlPlaneAssertion(subject: ControlPlaneAssertionSubject): string {
  return createSignedControlPlaneAssertion(serverEnv.controlPlaneInternalSecret, subject);
}
