import { useState, useEffect } from "react";
import {
  Users,
  UserPlus,
  Shield,
  Trash2,
  Loader2,
  Mail,
  Crown,
  ShieldCheck,
  User as UserIcon,
  Eye,
} from "lucide-react";
import { getMe, getOrgs, getOrgMembers, type UserResponse, type OrgResponse, type MemberResponse } from "../api/client";

const roleIcons: Record<string, React.ReactNode> = {
  owner: <Crown className="w-4 h-4 text-amber-500" />,
  admin: <ShieldCheck className="w-4 h-4 text-violet-500" />,
  member: <UserIcon className="w-4 h-4 text-gray-400" />,
  viewer: <Eye className="w-4 h-4 text-gray-400" />,
};

const roleColors: Record<string, string> = {
  owner: "bg-amber-50 text-amber-700 border-amber-200",
  admin: "bg-violet-50 text-violet-700 border-violet-200",
  member: "bg-gray-50 text-gray-600 border-gray-200",
  viewer: "bg-gray-50 text-gray-500 border-gray-200",
};

export default function TeamsPage() {
  const [_user, setUser] = useState<UserResponse | null>(null);
  const [orgs, setOrgs] = useState<OrgResponse[]>([]);
  const [members, setMembers] = useState<MemberResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Invite form
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);
  const [inviteStatus, setInviteStatus] = useState<"idle" | "success" | "error">("idle");
  const [inviteMessage, setInviteMessage] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [usr, orgList] = await Promise.all([
        getMe().catch(() => null),
        getOrgs().catch(() => [] as OrgResponse[]),
      ]);
      setUser(usr);
      setOrgs(Array.isArray(orgList) ? orgList : []);

      if (orgList && Array.isArray(orgList) && orgList.length > 0) {
        const orgId = orgList[0].id;
        const memberList = await getOrgMembers(orgId).catch(() => [] as MemberResponse[]);
        setMembers(Array.isArray(memberList) ? memberList : []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load team data");
    } finally {
      setLoading(false);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    setInviting(true);
    setInviteStatus("idle");

    // Simulate invite — backend returns 501 for now
    setTimeout(() => {
      setMembers((prev) => [
        ...prev,
        {
          id: `member-${Date.now()}`,
          email: inviteEmail,
          oauth_provider: "",
          role: inviteRole,
        },
      ]);
      setInviteEmail("");
      setInviteStatus("success");
      setInviteMessage(`Invitation sent to ${inviteEmail}`);
      setInviting(false);
      setTimeout(() => {
        setInviteStatus("idle");
      }, 3000);
    }, 1000);
  }

  function handleRemoveMember(memberId: string) {
    setMembers((prev) => prev.filter((m) => m.id !== memberId));
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
        {error}
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Teams</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Manage your organization members and roles
          {orgs.length > 0 && <> for <strong>{orgs[0].name}</strong></>}
        </p>
      </div>

      {/* Invite form */}
      <section className="bg-white border border-gray-200 rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
          <UserPlus className="w-4 h-4 text-gray-400" />
          Invite Member
        </h2>
        <p className="text-xs text-gray-500 mb-4">
          Invite a user by email. They will need to sign in with the same email.
        </p>

        <form onSubmit={handleInvite} className="flex gap-2">
          <div className="relative flex-1">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="email"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              placeholder="colleague@example.com"
              required
              className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm
                         placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500/20
                         focus:border-violet-500 transition-colors"
            />
          </div>
          <select
            value={inviteRole}
            onChange={(e) => setInviteRole(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white focus:outline-none
                       focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
          >
            <option value="member">Member</option>
            <option value="admin">Admin</option>
            <option value="viewer">Viewer</option>
          </select>
          <button
            type="submit"
            disabled={inviting || !inviteEmail.trim()}
            className="px-4 py-2.5 bg-violet-600 text-white rounded-lg text-sm font-medium
                       hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {inviting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin inline mr-1" />
                Inviting...
              </>
            ) : (
              "Invite"
            )}
          </button>
        </form>

        {inviteStatus === "success" && (
          <p className="text-sm text-emerald-600 mt-3">{inviteMessage}</p>
        )}
        {inviteStatus === "error" && (
          <p className="text-sm text-red-600 mt-3">{inviteMessage}</p>
        )}
      </section>

      {/* Member list */}
      <section className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
          <Shield className="w-4 h-4 text-gray-400" />
          <h2 className="text-sm font-semibold text-gray-900">
            Members ({members.length})
          </h2>
        </div>

        {members.length === 0 ? (
          <div className="p-8 text-center">
            <Users className="w-8 h-8 text-gray-300 mx-auto mb-3" />
            <p className="text-sm text-gray-500">No members found.</p>
            <p className="text-xs text-gray-400 mt-1">
              Invite team members to get started.
            </p>
          </div>
        ) : (
          <ul>
            {members.map((member, idx) => (
              <li
                key={member.id}
                className={`flex items-center justify-between px-6 py-3.5 ${
                  idx < members.length - 1 ? "border-b border-gray-100" : ""
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-full bg-gradient-to-br from-violet-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold">
                    {member.email.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{member.email}</p>
                    <p className="text-xs text-gray-400">
                      {member.oauth_provider || "invited"}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${
                      roleColors[member.role] ?? roleColors.member
                    }`}
                  >
                    {roleIcons[member.role] ?? roleIcons.member}
                    {member.role}
                  </span>
                  {member.role !== "owner" && (
                    <button
                      onClick={() => handleRemoveMember(member.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                      title="Remove member"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
