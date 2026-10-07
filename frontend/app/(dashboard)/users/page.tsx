'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/lib/store/auth';
import { listUsers, createUser, updateUser, deleteUser, User } from '@/lib/api/auth';
import { Shield, Plus, Trash2, UserPlus, Users as UsersIcon } from 'lucide-react';

export default function UsersPage() {
  const { user: currentUser, accessToken } = useAuthStore();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newUsername, setNewUsername] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newRole, setNewRole] = useState<'sub_admin' | 'user'>('user');
  const [creating, setCreating] = useState(false);

  const isOwner = currentUser?.role === 'owner';
  const isSubAdmin = currentUser?.role === 'sub_admin';

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const data = await listUsers(accessToken!);
      setUsers(data);
    } catch (e) {
      console.error('Failed to fetch users', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await createUser(accessToken!, { username: newUsername, password: newPassword, role: newRole });
      setNewUsername('');
      setNewPassword('');
      setShowCreate(false);
      await fetchUsers();
    } catch (e) {
      console.error('Failed to create user', e);
    } finally {
      setCreating(false);
    }
  };

  const handleToggleActive = async (u: User) => {
    try {
      await updateUser(accessToken!, u.id, { is_active: !u.is_active });
      await fetchUsers();
    } catch (e) {
      console.error('Failed to update user', e);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this user?')) return;
    try {
      await deleteUser(accessToken!, id);
      await fetchUsers();
    } catch (e) {
      console.error('Failed to delete user', e);
    }
  };

  const getRoleBadge = (role: string) => {
    const colors: Record<string, string> = {
      owner: 'bg-accent-primary/20 text-accent-primary',
      sub_admin: 'bg-accent-secondary/20 text-accent-secondary',
      user: 'bg-bg-tertiary text-text-secondary',
    };
    return colors[role] || 'bg-bg-tertiary text-text-secondary';
  };

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-text-primary mb-2">Users</h1>
          <p className="text-text-secondary">
            {isOwner ? 'Manage all users and sub-admins' : 'Manage your workers'}
          </p>
        </div>

        {(isOwner || isSubAdmin) && (
          <div className="mb-6">
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 transition-opacity"
            >
              <UserPlus className="w-4 h-4" />
              {showCreate ? 'Cancel' : 'Add User'}
            </button>
          </div>
        )}

        {showCreate && (isOwner || isSubAdmin) && (
          <form onSubmit={handleCreate} className="glass-card rounded-xl p-6 mb-6 space-y-4">
            <div>
              <label className="block text-text-primary font-medium mb-2">Username</label>
              <input
                type="text"
                value={newUsername}
                onChange={(e) => setNewUsername(e.target.value)}
                required
                minLength={3}
                className="w-full px-4 py-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary focus:outline-none focus:border-accent-primary"
              />
            </div>
            <div>
              <label className="block text-text-primary font-medium mb-2">Password</label>
              <input
                type="text"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                minLength={10}
                className="w-full px-4 py-2.5 bg-bg-tertiary border border-border rounded-lg text-text-primary focus:outline-none focus:border-accent-primary"
              />
            </div>
            {isOwner && (
              <div>
                <label className="block text-text-primary font-medium mb-2">Role</label>
                <div className="flex gap-2">
                  {(['sub_admin', 'user'] as const).map((role) => (
                    <button
                      key={role}
                      type="button"
                      onClick={() => setNewRole(role)}
                      className={`flex-1 py-2.5 rounded-lg text-sm font-medium capitalize transition-all ${
                        newRole === role
                          ? 'bg-gradient-to-r from-accent-primary to-accent-secondary text-white'
                          : 'bg-bg-tertiary text-text-secondary hover:text-text-primary'
                      }`}
                    >
                      {role.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <button
              type="submit"
              disabled={creating}
              className="px-4 py-2.5 rounded-lg bg-gradient-to-r from-accent-primary to-accent-secondary text-white font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {creating ? 'Creating...' : 'Create User'}
            </button>
          </form>
        )}

        {loading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="glass-card rounded-xl p-6 animate-pulse">
                <div className="h-5 bg-bg-tertiary rounded w-1/3 mb-4" />
                <div className="h-4 bg-bg-tertiary rounded w-full" />
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            {users.map((u) => (
              <div key={u.id} className="glass-card rounded-xl p-4 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-accent-primary to-accent-secondary flex items-center justify-center text-white font-bold">
                    {u.username.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-text-primary font-medium">{u.username}</span>
                      <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${getRoleBadge(u.role)}`}>
                        {u.role.replace('_', ' ')}
                      </span>
                      {!u.is_active && (
                        <span className="px-2 py-0.5 rounded text-xs font-medium bg-status-error/20 text-status-error">
                          Inactive
                        </span>
                      )}
                    </div>
                    <p className="text-text-muted text-xs mt-0.5">
                      {u.email || 'No email'} {u.last_login_at ? `• Last login ${new Date(u.last_login_at).toLocaleDateString()}` : ''}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {(isOwner || isSubAdmin) && u.id !== currentUser?.id && (
                    <>
                      <button
                        onClick={() => handleToggleActive(u)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                          u.is_active
                            ? 'bg-status-warning/20 text-status-warning hover:bg-status-warning/30'
                            : 'bg-status-success/20 text-status-success hover:bg-status-success/30'
                        }`}
                      >
                        {u.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                      <button
                        onClick={() => handleDelete(u.id)}
                        className="p-2 rounded-lg text-status-error hover:bg-status-error/10 transition-colors"
                        title="Delete user"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            ))}
            {users.length === 0 && (
              <div className="text-center py-12 text-text-muted">
                <UsersIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                <p>No users found</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
