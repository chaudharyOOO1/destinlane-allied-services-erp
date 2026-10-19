import Dashboard from './Dashboard';

// Management uses the same permission-scoped source records, rather than an
// independent estimate that counted gross invoices and repeated payroll joins.
export default function OwnerExecutiveView(){
  return <Dashboard endpoint="/owner/executive-summary" title="Management overview"/>;
}
