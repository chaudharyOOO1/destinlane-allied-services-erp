const SUPABASE_URL = 'https://zvogktuqdcpjsfargewg.supabase.co';
const SUPABASE_PUBLISHABLE_KEY = 'sb_publishable_nxCLI2Lj9Io__yHL2gxtTg_ybbfGWD4';

function headers(accessToken) {
  return {
    apikey: SUPABASE_PUBLISHABLE_KEY,
    'Content-Type': 'application/json',
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
  };
}

export async function requestPasswordRecovery(email, redirectTo) {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/recover`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ email, redirect_to: redirectTo }),
  });
  if (!response.ok) {
    let detail = 'Unable to start password recovery.';
    try { const data = await response.json(); detail = data?.msg || data?.message || detail; } catch {}
    throw new Error(detail);
  }
}

export async function updateRecoveredPassword(accessToken, password) {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    method: 'PUT',
    headers: headers(accessToken),
    body: JSON.stringify({ password }),
  });
  if (!response.ok) {
    let detail = 'Unable to update the password.';
    try { const data = await response.json(); detail = data?.msg || data?.message || detail; } catch {}
    throw new Error(detail);
  }
}
