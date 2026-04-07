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
import type { User, Session } from "@supabase/supabase-js";

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
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function fetchOrganizations(
  accessToken: string
): Promise<Organization[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.organizations ?? [];
  } catch {
    return [];
  }
}

function restoreActiveOrg(orgs: Organization[]): Organization | null {
  if (orgs.length === 0) return null;
  const savedId = localStorage.getItem(ACTIVE_ORG_KEY);
  return orgs.find((o) => o.id === savedId) ?? orgs[0];
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
        const orgs = await fetchOrganizations(s.access_token);
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
        const orgs = await fetchOrganizations(newSession.access_token);
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
