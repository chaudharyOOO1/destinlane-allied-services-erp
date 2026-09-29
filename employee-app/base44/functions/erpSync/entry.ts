import { createClientFromRequest } from 'npm:@base44/sdk@0.8.44';

async function updateSyncStatus(base44, configId, status, message) {
  await base44.asServiceRole.entities.ErpConfig.update(configId, {
    last_sync_at: new Date().toISOString(),
    last_sync_status: status,
    last_sync_message: message,
  });
}

function mapEmployee(emp) {
  const phone = String(emp.phone || emp.mobile || emp.contact || '');
  const code = String(emp.employee_code || emp.code || emp.emp_code || '');
  return {
    name: emp.name || emp.full_name || emp.employee_name || '—',
    phone,
    employee_code: code,
    designation: emp.designation || emp.role || emp.position || '',
    assigned_site: emp.site || emp.assigned_site || emp.location || emp.branch || '',
    monthly_salary: Number(emp.salary || emp.monthly_salary || emp.basic_pay || 0) || undefined,
    doj: emp.doj || emp.joining_date || emp.date_of_joining || undefined,
    bank_name: emp.bank_name || emp.bank || '',
    account_number: emp.account_number || emp.bank_account || '',
    status: String(emp.status || '').toLowerCase() === 'inactive' ? 'inactive' : 'active',
  };
}

export default async function(req) {
  try {
    const base44 = createClientFromRequest(req);

    let body = {};
    try { body = await req.json(); } catch { /* no body */ }
    const action = body.action || 'sync';

    // Load the single ErpConfig record
    const configs = await base44.asServiceRole.entities.ErpConfig.filter({}, '-updated_date', 1);
    if (!configs.length) {
      return Response.json({ error: 'No ERP configuration found. Save settings first.' }, { status: 400 });
    }
    const config = configs[0];

    if (!config.api_base_url) {
      return Response.json({ error: 'ERP API base URL not configured' }, { status: 400 });
    }

    const baseUrl = config.api_base_url.replace(/\/+$/, '');
    const headers = { 'Content-Type': 'application/json' };
    if (config.api_key) {
      headers['Authorization'] = `Bearer ${config.api_key}`;
    }

    // ---- TEST CONNECTION ----
    if (action === 'test') {
      const empEp = config.employee_endpoint || '/employees';
      try {
        const res = await fetch(`${baseUrl}${empEp}?limit=1`, { headers });
        if (!res.ok) {
          return Response.json({ ok: false, error: `ERP responded with ${res.status} ${res.statusText}` });
        }
        return Response.json({ ok: true, message: 'Connection successful — ERP is reachable.' });
      } catch (e) {
        return Response.json({ ok: false, error: e.message });
      }
    }

    let pulled = 0;
    let pushed = 0;

    // ---- PULL EMPLOYEES ----
    if (action === 'pull' || action === 'sync') {
      const empEp = config.employee_endpoint || '/employees';
      const res = await fetch(`${baseUrl}${empEp}`, { headers });
      if (!res.ok) {
        await updateSyncStatus(base44, config.id, 'failed', `Pull failed: ${res.status}`);
        return Response.json({ error: `ERP pull failed: ${res.status} ${res.statusText}` }, { status: 502 });
      }
      const data = await res.json();
      const employees = Array.isArray(data) ? data : (data.employees || data.data || data.results || []);

      for (const emp of employees) {
        const mapped = mapEmployee(emp);
        if (!mapped.phone && !mapped.employee_code) continue;

        let existing = [];
        if (mapped.phone) {
          existing = await base44.asServiceRole.entities.Employee.filter({ phone: mapped.phone });
        } else if (mapped.employee_code) {
          existing = await base44.asServiceRole.entities.Employee.filter({ employee_code: mapped.employee_code });
        }

        if (existing.length > 0) {
          await base44.asServiceRole.entities.Employee.update(existing[0].id, mapped);
        } else {
          await base44.asServiceRole.entities.Employee.create(mapped);
        }
        pulled++;
      }
    }

    // ---- PUSH ATTENDANCE ----
    if (action === 'push' || action === 'sync') {
      const attEp = config.attendance_endpoint || '/attendance';
      const records = await base44.asServiceRole.entities.Attendance.filter({}, '-date', 500);

      const res = await fetch(`${baseUrl}${attEp}`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ records }),
      });

      if (!res.ok) {
        await updateSyncStatus(base44, config.id, 'failed', `Push failed: ${res.status}`);
        return Response.json({ error: `ERP push failed: ${res.status} ${res.statusText}` }, { status: 502 });
      }
      pushed = records.length;
    }

    const msg = `Sync complete — pulled ${pulled} employees, pushed ${pushed} attendance records`;
    await updateSyncStatus(base44, config.id, 'success', msg);
    return Response.json({ ok: true, pulled, pushed, message: msg });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
}