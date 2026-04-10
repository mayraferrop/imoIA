"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { API_BASE, getAuthHeaders } from "@/lib/api";
import { t } from "@/lib/i18n";

interface Invite {
  id: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  created_at: string;
  organization_name: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800",
  accepted: "bg-green-100 text-green-800",
  revoked: "bg-red-100 text-red-800",
  expired: "bg-slate-100 text-slate-500",
};

export default function AdminInvitesPage() {
  const { activeOrg } = useAuth();
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const isAdmin = activeOrg?.role === "admin" || activeOrg?.role === "owner";

  const fetchInvites = useCallback(async () => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/v1/invites`, { headers });
      if (res.ok) {
        setInvites(await res.json());
      }
    } catch {
      // silencioso
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) fetchInvites();
    else setLoading(false);
  }, [isAdmin, fetchInvites]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError("");
    setSuccess("");

    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/v1/invites`, {
        method: "POST",
        headers,
        body: JSON.stringify({ email, role }),
      });

      if (res.ok) {
        setSuccess(t("admin.invites.create_success"));
        setEmail("");
        setRole("member");
        fetchInvites();
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || t("admin.invites.create_error"));
      }
    } catch {
      setError(t("admin.invites.create_error"));
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(inviteId: string) {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/v1/invites/${inviteId}`, {
        method: "DELETE",
        headers,
      });

      if (res.ok || res.status === 204) {
        setSuccess(t("admin.invites.revoke_success"));
        fetchInvites();
      }
    } catch {
      setError(t("admin.invites.revoke_error"));
    }
  }

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <p className="text-sm text-slate-500">{t("admin.no_permission")}</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl">
      <h1 className="text-xl font-bold text-slate-900 mb-1">
        {t("admin.invites.title")}
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        {t("admin.invites.subtitle")}
      </p>

      {/* Formulario de criacao */}
      <form
        onSubmit={handleCreate}
        className="bg-white rounded-xl border border-slate-200 p-5 mb-6"
      >
        <h2 className="text-sm font-semibold text-slate-700 mb-3">
          {t("admin.invites.new")}
        </h2>
        <div className="flex gap-3 items-end flex-wrap">
          <div className="flex-1 min-w-[200px]">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("auth.login.email_placeholder")}
              required
              className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
          </select>
          <button
            type="submit"
            disabled={creating}
            className="px-4 py-2 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
          >
            {creating
              ? t("common.loading")
              : t("admin.invites.send")}
          </button>
        </div>

        {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
        {success && <p className="text-sm text-green-600 mt-2">{success}</p>}
      </form>

      {/* Lista de invites */}
      <div className="bg-white rounded-xl border border-slate-200">
        {loading ? (
          <p className="p-5 text-sm text-slate-500">{t("common.loading")}</p>
        ) : invites.length === 0 ? (
          <p className="p-5 text-sm text-slate-500">
            {t("admin.invites.empty")}
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="px-5 py-3 font-medium">Email</th>
                <th className="px-5 py-3 font-medium">
                  {t("auth.invite.role")}
                </th>
                <th className="px-5 py-3 font-medium">Status</th>
                <th className="px-5 py-3 font-medium" />
              </tr>
            </thead>
            <tbody>
              {invites.map((inv) => (
                <tr key={inv.id} className="border-b border-slate-100 last:border-0">
                  <td className="px-5 py-3 text-slate-700">{inv.email}</td>
                  <td className="px-5 py-3 text-slate-600">{inv.role}</td>
                  <td className="px-5 py-3">
                    <span
                      className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[inv.status] || "bg-slate-100 text-slate-500"}`}
                    >
                      {inv.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-right">
                    {inv.status === "pending" && (
                      <button
                        onClick={() => handleRevoke(inv.id)}
                        className="text-xs text-red-600 hover:text-red-800 font-medium"
                      >
                        {t("admin.invites.revoke")}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
