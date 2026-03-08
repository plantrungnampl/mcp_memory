import { createHmac } from "node:crypto";

type ControlPlaneAssertionSubject = {
  id: string;
  email?: string | null;
};

type ControlPlaneAssertionPayload = {
  aud: "viberecall-control-plane";
  email: string | null;
  exp: number;
  iat: number;
  iss: "viberecall-web";
  sub: string;
};

const ASSERTION_TTL_SECONDS = 60;
const ASSERTION_VERSION = "v1";

function encodePayload(payload: ControlPlaneAssertionPayload): string {
  return Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
}

function signAssertionSegment(secret: string, segment: string): string {
  return createHmac("sha256", secret).update(segment).digest("base64url");
}

export function createSignedControlPlaneAssertion(
  secret: string,
  subject: ControlPlaneAssertionSubject,
): string {
  const issuedAt = Math.floor(Date.now() / 1000);
  const payload: ControlPlaneAssertionPayload = {
    aud: "viberecall-control-plane",
    email: subject.email ?? null,
    exp: issuedAt + ASSERTION_TTL_SECONDS,
    iat: issuedAt,
    iss: "viberecall-web",
    sub: subject.id,
  };
  const payloadSegment = encodePayload(payload);
  const unsignedToken = `${ASSERTION_VERSION}.${payloadSegment}`;
  const signature = signAssertionSegment(secret, unsignedToken);
  return `${unsignedToken}.${signature}`;
}
