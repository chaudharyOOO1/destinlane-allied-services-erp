const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_PUBLISHABLE_KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

export async function requestPasswordRecovery(email, redirectTo) {
  if (!SUPABASE_URL || !SUPABASE_PUBLISHABLE_KEY) {
    throw new Error('Email recovery configuration is missing. Contact your administrator.');
  }
  const url = new URL('/auth/v1/recover', SUPABASE_URL);
  url.searchParams.set('redirect_to', redirectTo);
  const response = await fetch(url, {
    method: 'POST',
    headers: { apikey: SUPABASE_PUBLISHABLE_KEY, 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    let detail = 'Unable to start password recovery.';
    try {
      const data = await response.json();
      detail = data?.msg || data?.message || detail;
    } catch { /* Keep the safe default when the response is not JSON. */ }
    throw new Error(detail);
  }
}
