import Link from "next/link";

import { LoginActions } from "@/components/login-actions";

type LoginScreenProps = {
  appUrl: string;
  hasSupabase: boolean;
};

export function LoginScreen({ appUrl, hasSupabase }: LoginScreenProps) {
  return (
    <main className="min-h-screen overflow-x-hidden bg-[#0A0A0F] text-[#F1ECFF]">
      <div className="mx-auto flex h-[72px] w-full max-w-[1440px] items-center px-4 sm:px-6 lg:px-8">
        <Link
          aria-label="Go to homepage"
          className="flex items-center gap-2 rounded-md transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#7A2DBE]/60"
          href="/"
        >
          <span className="size-2 rounded-full bg-[#7A2DBE]" />
          <span className="font-[family:var(--font-mono)] text-xs font-semibold tracking-[0.22em] text-[#EAE5FF]">
            VIBERECALL
          </span>
        </Link>
        <div className="ml-auto text-xs font-medium text-[#6F6790]">Secure access</div>
      </div>

      <section className="mx-auto flex min-h-[calc(100vh-72px)] w-full max-w-[1440px] items-center justify-center px-4 pb-6 pt-2 sm:px-6 sm:pb-8 sm:pt-3 lg:px-8">
        <div className="grid w-full max-w-[980px] rounded-3xl border border-[#1F1F23] bg-[#0B0820] md:h-[620px] md:grid-cols-[352px_minmax(0,1fr)] md:overflow-hidden">
          <aside className="hidden md:flex md:min-h-[620px] md:flex-col md:gap-4 md:bg-[#070519] md:px-7 md:py-7">
            <div className="h-[3px] w-10 rounded-sm bg-[#7A2DBE]" />
            <p className="text-[11px] font-bold tracking-[0.18em] text-[#A855F7]">WELCOME BACK</p>
            <h1 className="text-[24px] font-bold leading-tight text-[#F1ECFF]">
              Sign in to your
              <br />
              memory control plane
            </h1>
            <p className="text-sm text-[#7C7AA0]">
              Manage tokens, usage analytics, billing, and API logs from one workspace.
            </p>
            <div className="space-y-2 text-[13px] font-medium text-[#C9C5E8]">
              <p>- Real-time token and usage visibility</p>
              <p>- Project-scoped access and controls</p>
              <p>- Secure auth with Supabase callback</p>
            </div>
            <div className="mt-auto border-t border-[#1D1730] pt-4 text-xs text-[#6F6790]">
              Use your Google account or request a magic link.
            </div>
          </aside>

          <div className="min-w-0 rounded-3xl bg-[#0F0D2A] p-6 sm:p-8 md:min-h-[620px] md:rounded-none md:p-10">
            <div className="mb-5 rounded-xl border border-[#1F1B35] bg-[#120F2A] p-4 md:hidden">
              <p className="text-[11px] font-bold tracking-[0.18em] text-[#A855F7]">WELCOME BACK</p>
              <p className="mt-1 text-sm font-semibold leading-snug text-[#F1ECFF]">
                Sign in to your memory control plane.
              </p>
            </div>
            <p className="text-[11px] font-bold tracking-[0.16em] text-[#A855F7]">AUTHENTICATION</p>
            <h2 className="mt-1 text-4xl font-bold leading-tight text-[#F1ECFF]">Sign in</h2>
            <p className="mt-2 text-sm text-[#8B86AF]">
              Continue with Google or use an email magic link.
            </p>

            <div className="mt-5">
              <LoginActions appUrl={appUrl} enabled={hasSupabase} />
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
