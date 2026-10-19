import {
  Users, MapPin, Calendar, ClipboardList, ReceiptText, Landmark,
  LayoutDashboard, UserRound, BriefcaseBusiness, FileCheck2, WalletCards,
  CircleDollarSign, Building2, AlertTriangle, UserCog, Database,
} from 'lucide-react';

// Shared by sidebar and page search; AccessContext supplies the server grants.
export const NAV_GROUPS = [
  { label: 'Overview', items: [
    { icon: LayoutDashboard, label: 'Dashboard', path: '/erp' },
    { icon: Landmark, label: 'Management Dashboard', path: '/owner-executive' },
  ] },
  { label: 'Workforce', items: [
    { icon: UserRound, label: 'Staff Master', path: '/staff' },
    { icon: Users, label: 'Employees', path: '/employees' },
    { icon: BriefcaseBusiness, label: 'Recruitment', path: '/personnel' },
    { icon: Calendar, label: 'Rosters', path: '/rosters' },
    { icon: ClipboardList, label: 'Attendance', path: '/attendance' },
  ] },
  { label: 'Clients & sites', items: [
    { icon: BriefcaseBusiness, label: 'Clients', path: '/clients' },
    { icon: FileCheck2, label: 'Contracts & Rates', path: '/contracts' },
    { icon: MapPin, label: 'Sites & Deployment', path: '/sites' },
  ] },
  { label: 'Finance', items: [
    { icon: Landmark, label: 'Company Money', path: '/md-accounting' },
    { icon: ReceiptText, label: 'Travel Expenses', path: '/travel-expenses' },
    { icon: ReceiptText, label: 'Billing & Invoices', path: '/billing' },
    { icon: WalletCards, label: 'Payroll', path: '/payroll' },
    { icon: CircleDollarSign, label: 'Accounts & GST', path: '/accounts' },
  ] },
  { label: 'Administration', items: [
    { icon: Building2, label: 'Company Profile & Docs', path: '/company' },
    { icon: FileCheck2, label: 'Compliance', path: '/compliance' },
    { icon: AlertTriangle, label: 'Risk Controls', path: '/risks' },
    { icon: UserCog, label: 'User Management', path: '/users' },
    { icon: Database, label: 'IFSC Master', path: '/ifsc-master' },
  ] },
];
