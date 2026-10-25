import { Link } from 'react-router-dom';
export default function PageNotFound() {
  return <main className="flex min-h-screen items-center justify-center bg-slate-50 p-6"><div className="text-center">
    <p className="text-sm font-medium text-slate-500">DestinLane employee portal</p>
    <h1 className="mt-3 text-2xl font-semibold text-slate-900">Page not found</h1>
    <p className="mt-3 text-sm text-slate-600">Open the employee dashboard to continue.</p>
    <Link to="/" className="mt-5 inline-block rounded-lg border bg-white px-4 py-2 text-sm">Employee dashboard</Link>
  </div></main>;
}
