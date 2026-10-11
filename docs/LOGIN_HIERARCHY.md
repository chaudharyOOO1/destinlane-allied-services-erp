# Login hierarchy

The internal hierarchy is IT Super Admin → Management → HR → Staff → Employee.

IT Super Admin has business and system access, including management dashboards, company documents, staff accounts, employee approvals, attendance controls, payroll and finances. Management is the business administration role. Management, IT Super Admin and HR may create staff; ordinary departmental staff cannot.

Staff working capacity is defined by departmental roles (Operations, Accounts, Supervisor) and individual permissions. Workforce employees use Employee access. Existing external client access is retained separately.

Visible labels use the new hierarchy. Stable backend role codes retain existing accounts, JWT compatibility, database enums and permission keys: SUPER_ADMIN maps to IT Super Admin; OWNER maps to Management; legacy ADMIN appears as Management · Administrator; OPERATIONS/ACCOUNTS/SUPERVISOR appear under Staff; legacy STAFF means Employee. No existing account is promoted automatically and no identifiers or passwords are changed.

The former Owner Executive navigation item and page are Management Dashboard. The internal route remains compatible with saved links.
