import {lazy, Suspense} from 'react';
import WorkspaceErrorBoundary from './components/WorkspaceErrorBoundary';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { AccessProvider } from './context/AccessContext';
import { CompanyProvider } from './context/CompanyContext';
const CompanySettings = lazy(() => import('./pages/CompanySettings'));
const StaffMaster = lazy(() => import('./pages/StaffMaster'));
const TravelExpenses = lazy(() => import('./pages/TravelExpenses'));
const MDWorkspace = lazy(() => import('./pages/MDWorkspace'));
import ProtectedRoute from './components/ProtectedRoute';
const Login = lazy(() => import('./pages/Login'));
const AdminSetup = lazy(() => import('./pages/AdminSetup'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));
const AdminRecovery = lazy(() => import('./pages/AdminRecovery'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const ERPModules = lazy(() => import('./pages/ERPModules'));
const Employees = lazy(() => import('./pages/Employees'));
const Personnel = lazy(() => import('./pages/Personnel'));
const Clients = lazy(() => import('./pages/Clients'));
const Sites = lazy(() => import('./pages/Sites'));
const Contracts = lazy(() => import('./pages/Contracts'));
const Rosters = lazy(() => import('./pages/Rosters'));
const Attendance = lazy(() => import('./pages/Attendance'));
const ControlCenter = lazy(() => import('./pages/ControlCenter'));
const InvoicesView = lazy(() => import('./pages/InvoicesView'));
const OwnerExecutiveView = lazy(() => import('./pages/OwnerExecutiveView'));
const PayrollView = lazy(() => import('./pages/PayrollView'));
const UserManagement = lazy(() => import('./pages/UserManagement'));
const IfscMaster = lazy(() => import('./pages/IfscMaster'));
const AccountSettings = lazy(() => import('./pages/AccountSettings'));
import './App.css';

function App() {
  return <AuthProvider><AccessProvider><CompanyProvider><Router><WorkspaceErrorBoundary><Suspense fallback={<div role="status" className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-600">Loading workspace…</div>}><Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/admin-setup" element={<AdminSetup />} />
    <Route path="/forgot-password" element={<ForgotPassword />} />
    <Route path="/reset-password" element={<ResetPassword />} />
    <Route path="/admin-recovery" element={<AdminRecovery />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/staff" element={<StaffMaster />} />
      <Route path="/travel-expenses" element={<TravelExpenses />} />
      <Route path="/md-accounting" element={<MDWorkspace />} />
      <Route path="/company" element={<CompanySettings />} />
      <Route path="/erp" element={<ERPModules />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/employees" element={<Employees />} />
      <Route path="/personnel" element={<Personnel />} />
      <Route path="/clients" element={<Clients />} />
      <Route path="/contracts" element={<Contracts />} />
      <Route path="/sites" element={<Sites />} />
      <Route path="/rosters" element={<Rosters />} />
      <Route path="/attendance" element={<Attendance />} />
      <Route path="/billing" element={<InvoicesView />} />
      <Route path="/payroll" element={<PayrollView />} />
      <Route path="/accounts" element={<ControlCenter type="accounts" />} />
      <Route path="/compliance" element={<ControlCenter type="compliance" />} />
      <Route path="/risks" element={<ControlCenter type="risks" />} />
      <Route path="/owner-executive" element={<OwnerExecutiveView />} />
      <Route path="/users" element={<UserManagement />} />
      <Route path="/ifsc-master" element={<IfscMaster />} />
      <Route path="/account" element={<AccountSettings />} />
    </Route>
    <Route path="/" element={<Navigate to="/erp" replace />} />
    <Route path="*" element={<Navigate to="/erp" replace />} />
  </Routes></Suspense></WorkspaceErrorBoundary></Router></CompanyProvider></AccessProvider></AuthProvider>;
}
export default App;
