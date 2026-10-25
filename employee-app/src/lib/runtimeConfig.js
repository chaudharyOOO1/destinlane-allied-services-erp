/** Web uses the ERP origin; installed apps call the explicit HTTPS backend. */
export function employeeRuntime(native, configuredApi = '') {
  const configured = configuredApi.trim().replace(/\/+$/, '');
  if (configured && native) {
    const url = new URL(configured);
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash) {
      throw new Error('Native ERP API address must be HTTPS without credentials or query parameters.');
    }
  }
  const origin = configured || (native ? 'https://erp.destinlane.in' : '');
  return {apiBase: origin.endsWith('/api/v1') ? origin : `${origin}/api/v1`, routerBase: native ? '/' : '/employee'};
}
