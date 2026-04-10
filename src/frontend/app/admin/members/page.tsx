"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { API_BASE, getAuthHeaders } from "@/lib/api";
import { t } from "@/lib/i18n";

interface Member {
  user_id: string;
  email: string;
  role: string;
  created_at: string | null;
}

const ROLE_COLORS: Record<string, string> = {
  owner: "bg-purple-100 text-purple-800",
  admin: "bg-blue-100 text-blue-800",
  member: "bg-slate-100 text-slate-600",
};

export default function AdminMembersPage() {
  const { activeOrg, user } = useAuth();
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const isAdmin = activeOrg?.role === "admin" || activeOrg?.role === "owner";

  const fetchMembers = useCallback(async () => {
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/v1/members`, { headers });
      if (res.ok) {
        setMembers(await res.json());
      }
    } catch {
      // silencioso
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) fetchMembers();
    else setLoading(false);
  }, [isAdmin, fetchMembers]);

  async function handleRoleChange(userId: string, newRole: string) {
    setError("");
    setSuccess("");

    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/v1/members/${userId}/role`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ role: newRole }),
      });

      if (res.ok) {
        setSuccess(t("admin.members.role_updated"));
        fetchMembers();
      } else {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || t("admin.members.role_error"));
      }
    } catch {
      setError(t("admin.members.role_error"));
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
        {t("admin.members.title")}
      </h1>
      <p className="text-sm text-slate-500 mb-6">
        {t("admin.members.subtitle")}
      </p>

      {error && (
        <p className="text-sm text-red-600 mb-4 bg-red-50 p-3 rounded-lg">
          {error}
        </p>
      )}
      {success && (
        <p className="text-sm text-green-600 mb-4 bg-green-50 p-3 rounded-lg">
          {success}
        </p>
      )}

      <div className="bg-white rounded-xl border border-slate-200">
        {loading ? (
          <p className="p-5 text-sm text-slate-500">{t("common.loading")}</p>
        ) : members.length === 0 ? (
          <p className="p-5 text-sm text-slate-500">
            {t("admin.members.empty")}
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="px-5 py-3 font-medium">Email</th>
                <th className="px-5 py-3 font-medium">
                  {t("auth.invite.role")}
                </th>
                <th className="px-5 py-3 font-medium" />
              </tr>
            </thead>
            <tbody>
              {members.map((m) => {
                const isOwner = m.role === "owner";
                const isSelf = m.user_id === user?.id;
                return (
                  <tr
                    key={m.user_id}
                    className="border-b border-slate-100 last:border-0"
                  >
                    <td className="px-5 py-3 text-slate-700">
                      {m.email}
                      {isSelf && (
                        <span className="ml-2 text-xs text-slate-400">
                          ({t("admin.members.you")})
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[m.role] || "bg-slate-100"}`}
                      >
                        {m.role}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-right">
                      {!isOwner && !isSelf && (
                        <select
                          value={m.role}
                          onChange={(e) =>
                            handleRoleChange(m.user_id, e.target.value)
                          }
                          className="px-2 py-1 border border-slate-200 rounded text-xs focus:outline-none focus:ring-2 focus:ring-teal-500"
                        >
                          <option value="admin">Admin</option>
                          <option value="member">Member</option>
                        </select>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
