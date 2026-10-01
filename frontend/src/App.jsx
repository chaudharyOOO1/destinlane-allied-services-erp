import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { useAuth } from './context/useAuth';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import AdminSetup from './pages/AdminSetup';
import AdminRecovery from './pages/AdminRecovery';
import Dashboard from './pages/Dashboard';
import ERPModules from './pages/ERPModules';
import Employees from './pages/Employees';
import Personnel from './pages/Personnel';
import Clients from './pages/Clients';
import Sites from './pages/Sites';
import Rosters from './pages/Rosters';
import Attendance from './pages/Attendance';
import ControlCenter from './pages/ControlCenter';
import ClientsView from './pages/ClientsView';
import SitesView from './pages/SitesView';
import RosterView from './pages/RosterView';
import AttendanceView from './pages/AttendanceView';
import InvoicesView from './pages/InvoicesView';
import './App.css';
import OwnerExecutiveView from './pages/OwnerExecutiveView';
import PayrollView from './pages/PayrollView';
import AccountSettings from './pages/AccountSettings';
import UserManagement from './pages/UserManagement';
import IfscMaster from './pages/IfscMaster';

const INTERNAL = ['OWNER','SUPER_ADMIN','ADMIN'];
const HR_ROLES = [...INTERNAL, 'HR'];
const OPS_ROLES = [...INTERNAL, 'OPERATIONS', 'SUPERVISOR'];
const ACCOUNTS_ROLES = [...INTERNAL, 'ACCOUNTS'];
const CLIENT_ROLES = [...INTERNAL, 'CLIENT'];
const STAFF_ROLES = [...CLIENT_ROLES, 'STAFF'];
const ATTENDANCE_ROLES = [...HR_ROLES, 'OPERATIONS', 'SUPERVISOR', 'CLIENT', 'STAFF'];


function RootRedirect() { const { isAuthenticated } = useAuth(); return <Navigate to={isAuthenticated ? '/erp' : '/login'} replace />; }
function Protected({ children, allowedRoles, permission }) { return <ProtectedRoute allowedRoles={allowedRoles} permission={permission}>{children}</ProtectedRoute>; }

function App() {
  return <Router><AuthProvider><Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/setup-admin" element={<AdminSetup />} />
    <Route path="/admin-recovery" element={<AdminRecovery />} />
    <Route path="/erp" element={<Protected permission="dashboard.view"><ERPModules /></Protected>} />
    <Route path="/dashboard" element={<Protected permission="dashboard.view"><Dashboard /></Protected>} />
    <Route path="/employees" element={<Protected permission="employees.view"><Employees /></Protected>} />
    <Route path="/personnel" element={<Protected permission="employees.view"><Personnel /></Protected>} />
    <Route path="/clients" element={<Protected permission="clients.view"><Clients /></Protected>} />
    <Route path="/sites" element={<Protected permission="sites.view"><Sites /></Protected>} />
    <Route path="/rosters" element={<Protected permission="rosters.view"><Rosters /></Protected>} />
    <Route path="/attendance" element={<Protected permission="attendance.view"><Attendance /></Protected>} />
    <Route path="/billing" element={<Protected permission="billing.view"><InvoicesView /></Protected>} />
    <Route path="/payroll" element={<Protected permission="payroll.view"><PayrollView /></Protected>} />
    <Route path="/accounts" element={<Protected permission="finance.view"><ControlCenter type="accounts" /></Protected>} />
    <Route path="/compliance" element={<Protected permission="compliance.view"><ControlCenter type="compliance" /></Protected>} />
    <Route path="/risks" element={<Protected permission="risks.view"><ControlCenter type="risks" /></Protected>} />
    <Route path="/owner-executive" element={<Protected permission="owner.view"><OwnerExecutiveView /></Protected>} />
    <Route path="/users" element={<Protected permission="user_management.view"><UserManagement /></Protected>} />
    <Route path="/ifsc-master" element={<Protected allowedRoles={["OWNER","SUPER_ADMIN","ADMIN"]} permission="user_management.view"><IfscMaster /></Protected>} />
    <Route path="/account" element={<Protected><AccountSettings /></Protected>} />
    <Route path="/" element={<RootRedirect />} /><Route path="*" element={<RootRedirect />} />
  </Routes></AuthProvider></Router>;
}
export default App;
