import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/useAuth';
import {
  ArrowRight,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  LockKeyhole,
  Mail,
  ShieldCheck,
} from 'lucide-react';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const { login, loading, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) navigate('/dashboard', { replace: true });
  }, [isAuthenticated, navigate]);

  async function handleSubmit(event) {
    event.preventDefault();
    setError('');

    const result = await login(email.trim(), password);

    if (result.success) {
      navigate('/dashboard', { replace: true });
    } else {
      setError(result.error || 'Unable to sign in. Please check your credentials.');
    }
  }

  return (
    <main className="min-h-screen bg-[#f7f9fc] text-slate-900">
      <div className="grid min-h-screen lg:grid-cols-[1.08fr_0.92fr]">
        <section className="relative hidden overflow-hidden bg-[#0b1720] lg:flex">
          <div className="absolute inset-0">
            <div className="absolute -left-28 top-[-180px] h-[520px] w-[520px] rounded-full bg-teal-500/10 blur-3xl" />
            <div className="absolute -right-28 bottom-[-180px] h-[520px] w-[520px] rounded-full bg-cyan-400/10 blur-3xl" />
            <div
              className="absolute inset-0 opacity-[0.055]"
              style={{
                backgroundImage:
                  'linear-gradient(rgba(255,255,255,.9) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.9) 1px, transparent 1px)',
                backgroundSize: '56px 56px',
              }}
            />
          </div>

          <div className="relative flex w-full flex-col justify-between px-12 py-10 xl:px-20 xl:py-12">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white shadow-lg">
                <ShieldCheck className="h-6 w-6 text-[#0b1720]" />
              </div>
              <div>
                <p className="text-[17px] font-bold tracking-[0.01em] text-white">
                  DestinLane
                </p>
                <p className="text-[9px] font-semibold uppercase tracking-[0.28em] text-slate-400">
                  Allied Services ERP
                </p>
              </div>
            </div>

            <div className="max-w-xl pb-4">
              <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-[11px] font-medium text-slate-300">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                Secure enterprise workspace
              </div>

              <h1 className="text-4xl font-semibold leading-[1.08] tracking-[-0.035em] text-white xl:text-6xl">
                One workspace for your entire workforce.
              </h1>

              <p className="mt-6 max-w-lg text-[15px] leading-7 text-slate-400 xl:text-base">
                Manage employees, clients, sites, rosters, attendance, payroll,
                billing and compliance from one controlled operational platform.
              </p>

              <div className="mt-10 grid max-w-lg grid-cols-2 gap-3">
                {[
                  ['Workforce', 'Employee management'],
                  ['Operations', 'Sites & rosters'],
                  ['Finance', 'Payroll & billing'],
                  ['Compliance', 'Documents & controls'],
                ].map(([title, description]) => (
                  <div
                    key={title}
                    className="rounded-xl border border-white/10 bg-white/[0.035] px-4 py-3"
                  >
                    <p className="text-sm font-semibold text-slate-200">{title}</p>
                    <p className="mt-1 text-[11px] text-slate-500">{description}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] text-slate-500">
              <span>Destinlane Allied Services Pvt Ltd</span>
              <span className="hidden sm:inline">•</span>
              <span>Authorized access only</span>
            </div>
          </div>
        </section>

        <section className="flex min-h-screen items-center justify-center px-5 py-8 sm:px-8">
          <div className="w-full max-w-[430px]">
            <div className="mb-10 flex items-center gap-3 lg:hidden">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#0b1720]">
                <ShieldCheck className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="font-bold tracking-tight text-slate-900">DestinLane</p>
                <p className="text-[9px] font-semibold uppercase tracking-[0.24em] text-slate-400">
                  Allied Services ERP
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-7 shadow-[0_20px_60px_rgba(15,23,42,0.07)] sm:p-9">
              <div className="mb-8">
                <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-teal-700">
                  Enterprise portal
                </p>
                <h2 className="mt-3 text-3xl font-semibold tracking-[-0.025em] text-slate-950">
                  Welcome back
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-500">
                  Sign in with your authorized account to access the ERP.
                </p>
              </div>

              {error && (
                <div
                  role="alert"
                  className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm leading-5 text-red-700"
                >
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label
                    htmlFor="email"
                    className="mb-2 block text-sm font-semibold text-slate-700"
                  >
                    Login ID / Email
                  </label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      id="email"
                      type="email"
                      autoComplete="username"
                      autoFocus
                      required
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                      className="h-12 w-full rounded-xl border border-slate-300 bg-white pl-10 pr-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:ring-4 focus:ring-teal-600/10"
                      placeholder="Enter your login ID"
                    />
                  </div>
                </div>

                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <label
                      htmlFor="password"
                      className="block text-sm font-semibold text-slate-700"
                    >
                      Password
                    </label>
                  </div>

                  <div className="relative">
                    <LockKeyhole className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      autoComplete="current-password"
                      required
                      value={password}
                      onChange={(event) => setPassword(event.target.value)}
                      className="h-12 w-full rounded-xl border border-slate-300 bg-white pl-10 pr-12 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-teal-600 focus:ring-4 focus:ring-teal-600/10"
                      placeholder="Enter your password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((visible) => !visible)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                    >
                      {showPassword ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-[#0b1720] text-sm font-semibold text-white shadow-sm transition hover:bg-[#142631] focus:outline-none focus:ring-4 focus:ring-slate-900/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Signing in...
                    </>
                  ) : (
                    <>
                      Sign in
                      <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </form>

              <div className="mt-7 border-t border-slate-100 pt-6">
                <button
                  type="button"
                  onClick={() => navigate('/setup-admin')}
                  className="mx-auto flex items-center gap-2 text-sm font-medium text-slate-500 transition hover:text-slate-900"
                >
                  <KeyRound className="h-4 w-4" />
                  First-time administrator setup
                </button>
              </div>
            </div>

            <div className="mt-6 text-center">
              <p className="text-[11px] leading-5 text-slate-400">
                © {new Date().getFullYear()} Destinlane Allied Services Pvt Ltd
              </p>
              <p className="mt-1 text-[10px] uppercase tracking-[0.14em] text-slate-300">
                DestinLane Allied Services ERP
              </p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
