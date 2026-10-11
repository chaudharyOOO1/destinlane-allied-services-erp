export const loginHierarchy = ['IT Super Admin', 'Management', 'HR', 'Staff', 'Employee'];

// Stable API role codes retain existing accounts and permissions.
const labels = {
  SUPER_ADMIN: 'IT Super Admin',
  OWNER: 'Management',
  ADMIN: 'Management · Administrator',
  HR: 'HR',
  OPERATIONS: 'Staff · Operations',
  ACCOUNTS: 'Staff · Accounts',
  SUPERVISOR: 'Staff · Supervisor',
  STAFF: 'Employee',
  CLIENT: 'Client',
};

export function roleLabel(role) {
  return labels[role] || role || 'Account';
}
