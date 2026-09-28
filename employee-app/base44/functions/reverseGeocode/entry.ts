import { createClientFromRequest } from 'npm:@base44/sdk@0.8.44';

/** Builds a short, human-readable place label from a Nominatim response. */
function formatPlace(data) {
  if (!data) return '';
  const a = data.address || {};
  const parts = [
    a.road || a.pedestrian || a.neighbourhood || a.suburb,
    a.suburb || a.city_district,
    a.city || a.town || a.village || a.county,
    a.state,
  ].filter(Boolean);
  const unique = [...new Set(parts)];
  return unique.slice(0, 3).join(', ') || data.display_name || '';
}

export default async function (req) {
  try {
    const base44 = createClientFromRequest(req);
    const user = await base44.auth.me();
    if (!user) return Response.json({ error: 'Unauthorized' }, { status: 401 });

    let body = {};
    try { body = await req.json(); } catch { /* no body */ }

    const lat = Number(body.lat);
    const lng = Number(body.lng);
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) {
      return Response.json({ error: 'Valid lat and lng are required' }, { status: 400 });
    }

    const url = `https://nominatim.openstreetmap.org/reverse?format=json&zoom=16&addressdetails=1&lat=${lat}&lon=${lng}`;
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'FAS-Attendance/1.0 (Fortellus Allied Services attendance app)',
        Accept: 'application/json',
      },
    });

    if (!res.ok) {
      return Response.json({ error: `Geocoder responded with ${res.status}` }, { status: 502 });
    }

    const data = await res.json();
    return Response.json({ place: formatPlace(data) });
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
}