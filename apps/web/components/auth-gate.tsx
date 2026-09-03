"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useResource } from "@/lib/api";

export type AuthSession = {
  authenticated: boolean;
  anonymous_development?: boolean;
  authentication_required?: boolean;
  onboarding_required?: boolean;
  user?: { id: string; email: string; name: string };
  organization?: { id: string; name: string };
  role?: string;
};

export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data, loading, error } = useResource<AuthSession>("/auth/session");
  const authenticationPage = pathname === "/login";

  useEffect(() => {
    if (!data) return;
    if (data.authentication_required && !authenticationPage) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    } else if (data.authenticated && authenticationPage) {
      router.replace(data.onboarding_required ? "/onboarding" : "/");
    }
  }, [authenticationPage, data, pathname, router]);

  if (loading && !authenticationPage) {
    return (
      <main className="min-h-screen grid place-items-center bg-[#f7f7f3]">
        <div className="flex items-center gap-3 text-sm text-[#657064]">
          <Loader2 className="animate-spin" size={18} /> Opening your workspace…
        </div>
      </main>
    );
  }
  if (error && !authenticationPage) return <>{children}</>;
  if (data?.authentication_required && !authenticationPage) return null;
  return <>{children}</>;
}
