"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { createClient } from "@/lib/supabase/client";
import type { SupabaseClient, User, Session } from "@supabase/supabase-js";

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export interface Organization {
  id: string;
  name: string;
  slug: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  session: Session | null;
  organizations: Organization[];
  activeOrg: Organization | null;
  setActiveOrg: (org: Organization) => void;
  loading: boolean;
  signOut: () => Promise<void>;
}

const ACTIVE_ORG_KEY = "imoia_active_org_id";

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AuthContext = createContext<AuthContextType>({
  user: null,
  session: null,
  organizations: [],
  activeOrg: null,
  setActiveOrg: () => {},
  loading: true,
  signOut: async () => {},
});

async function fetchOrganizationsViaRLS(
  supabase: SupabaseClient,
  userId: string
): Promise<Organization[]> {
  const { data, error } = await supabase
    .from("organization_members")
    .select("role, organizations(id, name, slug)")
    .eq("user_id", userId);

  if (error || !data) return [];

  return data.map((m: Record<string, unknown>) => {
    const org = m.organizations as Record<string, string> | null;
    return {
      id: org?.id ?? "",
      name: org?.name ?? "",
      slug: org?.slug ?? "",
      role: (m.role as string) ?? "member",
    };
  });
}

function restoreActiveOrg(orgs: Organization[]): Organization | null {
  if (orgs.length === 0) return null;
  const savedId = localStorage.getItem(ACTIVE_ORG_KEY);
  const org = orgs.find((o) => o.id === savedId) ?? orgs[0];
  if (org) localStorage.setItem(ACTIVE_ORG_KEY, org.id);
  return org;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [activeOrg, setActiveOrgState] = useState<Organization | null>(null);
  const [loading, setLoading] = useState(true);

  const supabase = createClient();

  const setActiveOrg = useCallback((org: Organization) => {
    setActiveOrgState(org);
    localStorage.setItem(ACTIVE_ORG_KEY, org.id);
  }, []);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setUser(null);
    setSession(null);
    setOrganizations([]);
    setActiveOrgState(null);
    localStorage.removeItem(ACTIVE_ORG_KEY);
  }, [supabase.auth]);

  // Inicializacao + listener de auth state
  useEffect(() => {
    async function init() {
      const {
        data: { session: s },
      } = await supabase.auth.getSession();

      if (s?.user) {
        setUser(s.user);
        setSession(s);
        const orgs = await fetchOrganizationsViaRLS(supabase, s.user.id);
        setOrganizations(orgs);
        setActiveOrgState(restoreActiveOrg(orgs));
      }

      setLoading(false);
    }

    init();

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ?? null);

      if (event === "SIGNED_IN" && newSession) {
        const orgs = await fetchOrganizationsViaRLS(supabase, newSession.user.id);
        setOrganizations(orgs);
        setActiveOrgState(restoreActiveOrg(orgs));
      } else if (event === "SIGNED_OUT") {
        setOrganizations([]);
        setActiveOrgState(null);
        localStorage.removeItem(ACTIVE_ORG_KEY);
      }
    });

    return () => subscription.unsubscribe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        organizations,
        activeOrg,
        setActiveOrg,
        loading,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useAuth() {
  return useContext(AuthContext);
}
