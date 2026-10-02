import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import Login from './pages/Login';
import AdminSetup from './pages/AdminSetup';
import ForgotPassword from './pages/ForgotPassword';
import Dashboard from './pages/Dashboard';
import ERPModules from './pages/ERPModules';
import Employees from './pages/Employees';
import Personnel from './pages/Personnel';
import Clients from './pages/Clients';
import Sites from './pages/Sites';
import Rosters from './pages/Rosters';
import Attendance from './pages/Attendance';
import ControlCenter from './pages/ControlCenter';
import InvoicesView from './pages/InvoicesView';
import OwnerExecutiveView from './pages/OwnerExecutiveView';
import PayrollView from './pages/PayrollView';
import UserManagement from './pages/UserManagement';
import IfscMaster from './pages/IfscMaster';
import './App.css';

function App() {
  return <AuthProvider><Router><Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/admin-setup" element={<AdminSetup />} />
    <Route path="/forgot-password" element={<ForgotPassword />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/erp" element={<ERPModules />} />
      <Route path="/dashboard" element={<Dashboard />} />
      <Route path="/employees" element={<Employees />} />
      <Route path="/personnel" element={<Personnel />} />
      <Route path="/clients" element={<Clients />} />
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
    </Route>
    <Route path="/" element={<Navigate to="/erp" replace />} />
    <Route path="*" element={<Navigate to="/erp" replace />} />
  </Routes></Router></AuthProvider>;
}
export default App;
