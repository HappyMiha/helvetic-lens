"use client";

import { createContext, useContext, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useResource } from "@/lib/api";

export type AuthSession = {
  authenticated: boolean;
  anonymous_development?: boolean;
  authentication_required?: boolean;
  onboarding_required?: boolean;
  user?: { id: string; email: string; name: string; email_verified?: boolean };
  organization?: { id: string; name: string };
  role?: string;
  platform_admin?: boolean;
  organizations?: Array<{
    id: string;
    name: string;
    role: string;
    current: boolean;
  }>;
};

const AuthContext = createContext<AuthSession | null>(null);

export function useAuth() {
  const session = useContext(AuthContext);
  return {
    session,
    canManage: !session?.authenticated || session.role === "organization_admin",
    isPlatformAdmin: !session?.authenticated || !!session.platform_admin,
  };
}

export function AdminOnly({ children }: { children: React.ReactNode }) {
  return useAuth().canManage ? <>{children}</> : null;
}

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
      const parameters = new URLSearchParams(window.location.search);
      const invitation = parameters.get("invite");
      if (parameters.get("verify") || parameters.get("reset")) return;
      router.replace(
        invitation
          ? `/organization?invite=${encodeURIComponent(invitation)}`
          : data.onboarding_required
            ? "/onboarding"
            : "/",
      );
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
  return <AuthContext.Provider value={data}>{children}</AuthContext.Provider>;
}
