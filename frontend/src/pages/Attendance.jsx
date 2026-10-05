import { useCallback, useEffect, useState } from "react";
import MainLayout from "../layouts/MainLayout";
import api from "../api/axios";
import { useAccess } from "../context/AccessContext";
import { useAuth } from "../context/AuthContext";
const input =
  "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm";
const button =
  "rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50";
const today = () =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
const clock = (v) =>
  v
    ? new Date(v).toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        dateStyle: "short",
        timeStyle: "short",
      })
    : "—";
const fail = (e) =>
  typeof e.response?.data?.detail === "string"
    ? e.response.data.detail
    : "Check the details and try again.";
const blankRule = {
  site_id: "",
  shift_type: "DAY",
  start_time: "08:00",
  duty_hours: 8,
  grace_minutes: 15,
  version: 0,
  reason: "",
};
const blankCorrection = {
  roster_id: "",
  version: 0,
  assigned_to: "",
  status: "present",
  check_in_time: "",
  check_out_time: "",
  reason: "",
};
function Field({ label, children }) {
  return (
    <label className="block text-sm font-medium text-slate-600">
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  );
}
export default function Attendance() {
  const { can } = useAccess();
  const { user } = useAuth();
  const owner = user?.role === "OWNER";
  const [tab, setTab] = useState("register"),
    [rows, setRows] = useState([]),
    [requests, setRequests] = useState([]),
    [options, setOptions] = useState({
      sites: [],
      rules: [],
      employees: [],
      approvers: [],
    }),
    [filters, setFilters] = useState({ start: "", end: "", site_id: "" }),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [selected, setSelected] = useState(null),
    [history, setHistory] = useState([]),
    [reason, setReason] = useState(""),
    [rule, setRule] = useState(blankRule),
    [correction, setCorrection] = useState(blankCorrection),
    [rosterDate, setRosterDate] = useState(today),
    [rosters, setRosters] = useState([]),
    [access, setAccess] = useState({ employee_id: "", pin: "", reason: "" });
  const load = useCallback(async () => {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v),
    );
    const [a, c, o] = await Promise.all([
      api.get("/erp/attendance", { params }),
      api.get("/erp/attendance/corrections"),
      api.get("/erp/attendance/options"),
    ]);
    setRows(a.data);
    setRequests(c.data);
    setOptions(o.data);
    setLoading(false);
  }, [filters]);
  useEffect(() => {
    load().catch((e) => {
      setError(fail(e));
      setLoading(false);
    });
  }, [load]);
  useEffect(() => {
    if (tab === "corrections")
      api
        .get("/erp/attendance/correction-rosters", {
          params: { roster_date: rosterDate },
        })
        .then((r) => setRosters(r.data))
        .catch((e) => setError(fail(e)));
  }, [tab, rosterDate]);
  async function act(fn, success) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
      await load();
      setMessage(success);
    } catch (e) {
      setError(fail(e));
    } finally {
      setBusy(false);
    }
  }
  async function inspect(row) {
    setSelected(row);
    setReason("");
    try {
      setHistory((await api.get(`/erp/attendance/${row.id}/history`)).data);
    } catch (e) {
      setError(fail(e));
    }
  }
  async function selfie(kind) {
    try {
      const { data } = await api.post(
        `/erp/attendance/${selected.id}/selfie/${kind}/sign`,
      );
      window.open(data.url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setError(fail(e));
    }
  }
  function chooseRule(site, shift) {
    const found = options.rules.find(
      (r) => r.site_id === Number(site) && r.shift_type === shift,
    );
    setRule(
      found
        ? {
            ...blankRule,
            shift_type: shift,
            duty_hours: found.duty_hours,
            grace_minutes: found.grace_minutes,
            version: found.version,
            site_id: String(site),
            start_time: found.start_time.slice(0, 5),
            reason: "",
          }
        : { ...blankRule, site_id: site, shift_type: shift },
    );
  }
  async function exportRows() {
    try {
      const params = Object.fromEntries(
        Object.entries(filters).filter(([, v]) => v),
      );
      const r = await api.get("/erp/attendance/reports/export", {
        params,
        responseType: "blob",
      });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "DestinLane_Attendance.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(fail(e));
    }
  }
  const summary = [
    ["Records", rows.length],
    [
      "Open shifts",
      rows.filter((r) => r.verification_status === "OPEN").length,
    ],
    [
      "Awaiting review",
      rows.filter((r) => r.verification_status === "PENDING_REVIEW").length,
    ],
    [
      "Approved hours",
      rows
        .filter((r) => r.verification_status === "VERIFIED")
        .reduce(
          (n, r) =>
            n + Number(r.shift_hours || 0) + Number(r.overtime_hours || 0),
          0,
        )
        .toFixed(2),
    ],
  ];
  return (
    <MainLayout>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Attendance Master</h1>
        <p className="mt-1 text-sm text-slate-500">
          Workforce attendance, shift review and corrections. The register shows up to 1,000 matching records. Export covers your selected dates, or the current month when dates are empty. All times are
          shown in India time.
        </p>
      </div>
      {error && (
        <div
          role="alert"
          className="mb-4 rounded-lg bg-red-50 p-3 text-sm text-red-700"
        >
          {error}
        </div>
      )}
      {message && (
        <div
          role="status"
          className="mb-4 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700"
        >
          {message}
        </div>
      )}
      <div className="mb-5 grid gap-3 sm:grid-cols-4">
        {summary.map(([label, value]) => (
          <div
            key={label}
            className="rounded-xl border border-slate-200 bg-white p-4"
          >
            <div className="text-xs text-slate-500">{label}</div>
            <div className="mt-1 text-2xl font-semibold text-slate-900">
              {value}
            </div>
          </div>
        ))}
      </div>
      <div className="mb-5 flex flex-wrap gap-2">
        {[
          ["register", "Attendance register"],
          ["corrections", "Correction requests"],
          ...(owner
            ? [
                ["rules", "Shift rules"],
                ["access", "Employee access & devices"],
              ]
            : []),
        ].map(([key, label]) => (
          <button
            type="button"
            key={key}
            onClick={() => {
              setTab(key);
              setSelected(null);
            }}
            className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === key ? "bg-slate-900 text-white" : "border border-slate-200 bg-white text-slate-600"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {tab === "register" && (
        <>
          <div className="mb-4 grid gap-3 rounded-xl border border-slate-200 bg-white p-4 sm:grid-cols-4">
            <Field label="From">
              <input
                className={input}
                type="date"
                value={filters.start}
                onChange={(e) =>
                  setFilters({ ...filters, start: e.target.value })
                }
              />
            </Field>
            <Field label="To">
              <input
                className={input}
                type="date"
                value={filters.end}
                onChange={(e) =>
                  setFilters({ ...filters, end: e.target.value })
                }
              />
            </Field>
            <Field label="Site">
              <select
                className={input}
                value={filters.site_id}
                onChange={(e) =>
                  setFilters({ ...filters, site_id: e.target.value })
                }
              >
                <option value="">All sites</option>
                {options.sites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.site_name}
                  </option>
                ))}
              </select>
            </Field>
            {can("attendance.export") && (
              <button className={button} type="button" onClick={exportRows}>
                Export report
              </button>
            )}
          </div>
          <div className="overflow-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full whitespace-nowrap text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  {[
                    "Date / shift",
                    "Employee",
                    "Site",
                    "Status",
                    "Check-in / out",
                    "Regular / OT",
                    "GPS",
                    "Review",
                    "",
                  ].map((x, i) => (
                    <th className="p-3" key={i}>
                      {x}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-t border-slate-100">
                    <td className="p-3">
                      {r.attendance_date}
                      <div className="text-xs text-slate-400">
                        {r.shift_type}
                      </div>
                    </td>
                    <td className="p-3">
                      {r.name}
                      <div className="text-xs text-slate-400">
                        {r.employee_code}
                      </div>
                    </td>
                    <td className="p-3">{r.site_name || "—"}</td>
                    <td className="p-3 capitalize">{r.status}</td>
                    <td className="p-3">
                      {clock(r.check_in_time)}
                      <div>{clock(r.check_out_time)}</div>
                    </td>
                    <td className="p-3">
                      {Number(r.shift_hours || 0).toFixed(2)}h /{" "}
                      {Number(r.overtime_hours || 0).toFixed(2)}h
                    </td>
                    <td className="p-3">
                      <span
                        className={
                          r.is_geofence_verified
                            ? "text-emerald-700"
                            : "text-amber-700"
                        }
                      >
                        {r.is_geofence_verified ? "Within geofence" : "Manual"}
                      </span>
                      <div className="text-xs text-slate-400">
                        {r.check_in_distance_m != null
                          ? `${Math.round(r.check_in_distance_m)}m`
                          : ""}
                      </div>
                    </td>
                    <td className="p-3">
                      {r.verification_status?.replaceAll("_", " ")}
                    </td>
                    <td className="p-3">
                      <button
                        type="button"
                        className="font-medium text-blue-700"
                        onClick={() => inspect(r)}
                      >
                        Review & history
                      </button>
                    </td>
                  </tr>
                ))}
                {!rows.length && (
                  <tr>
                    <td colSpan={9} className="p-8 text-center text-slate-500">
                      {loading
                        ? "Loading attendance…"
                        : "No attendance recorded for these filters."}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          {selected && (
            <section className="mt-5 rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex justify-between">
                <h2 className="font-semibold text-slate-900">
                  {selected.name} · {selected.attendance_date}
                </h2>
                <button type="button" onClick={() => setSelected(null)}>
                  Close
                </button>
              </div>
              <p className="mt-2 text-sm text-slate-500">
                Late: {selected.late_minutes || 0} minutes · Source:{" "}
                {selected.source} · Version: {selected.version}
              </p>
              <div className="my-3 flex gap-3">
                {selected.has_check_in_selfie && (
                  <button
                    type="button"
                    onClick={() => selfie("check-in")}
                    className="text-sm text-blue-700"
                  >
                    View check-in selfie
                  </button>
                )}
                {selected.has_check_out_selfie && (
                  <button
                    type="button"
                    onClick={() => selfie("check-out")}
                    className="text-sm text-blue-700"
                  >
                    View check-out selfie
                  </button>
                )}
              </div>
              {can("attendance.approve") &&
                selected.verification_status === "PENDING_REVIEW" && (
                  <form
                    onSubmit={(e) => {
                      e.preventDefault();
                      act(async () => {
                        await api.post(
                          `/erp/attendance/${selected.id}/review`,
                          {
                            version: selected.version,
                            decision: "APPROVE",
                            reason,
                          },
                        );
                        setSelected(null);
                      }, "Attendance approved for payroll and billing.");
                    }}
                    className="flex flex-wrap gap-2"
                  >
                    <input
                      aria-label="Review reason"
                      className={`${input} max-w-md`}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      minLength={3}
                      maxLength={1000}
                      required
                      placeholder="Review remarks"
                    />
                    <button disabled={busy} className={button}>
                      Approve attendance & OT
                    </button>
                    <button
                      disabled={busy || reason.trim().length < 3}
                      type="button"
                      className="rounded-lg border border-red-200 px-4 text-sm text-red-700"
                      onClick={() =>
                        act(async () => {
                          await api.post(
                            `/erp/attendance/${selected.id}/review`,
                            {
                              version: selected.version,
                              decision: "REJECT",
                              reason,
                            },
                          );
                          setSelected(null);
                        }, "Attendance rejected. Submit a correction if required.")
                      }
                    >
                      Reject
                    </button>
                  </form>
                )}
              <h3 className="mb-2 mt-5 text-sm font-semibold">Audit history</h3>
              <div className="space-y-2">
                {history.map((h) => (
                  <div
                    key={h.id}
                    className="rounded-lg bg-slate-50 p-3 text-sm"
                  >
                    <div>
                      {h.action.replaceAll("_", " ")} · {clock(h.created_at)}
                    </div>
                    <p className="text-slate-500">
                      {h.details.reason ||
                        `Roster ${h.details.roster_id || ""}`}
                    </p>
                  </div>
                ))}
                {!history.length && (
                  <p className="text-sm text-slate-500">No recorded history.</p>
                )}
              </div>
            </section>
          )}
        </>
      )}
      {tab === "corrections" && (
        <>
          <p className="mb-4 text-sm text-slate-500">
            Recorded attendance stays unchanged until the assigned reviewer
            approves. Corrections are marked manual and retain the original
            punch evidence.
          </p>
          {can("attendance.edit") && (
            <form
              className="mb-5 grid gap-3 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-3"
              onSubmit={(e) => {
                e.preventDefault();
                const worked = ["present", "late"].includes(correction.status);
                act(async () => {
                  await api.post("/erp/attendance/corrections", {
                    ...correction,
                    roster_id: Number(correction.roster_id),
                    assigned_to: Number(correction.assigned_to),
                    check_in_time: worked
                      ? `${correction.check_in_time}:00+05:30`
                      : null,
                    check_out_time: worked
                      ? `${correction.check_out_time}:00+05:30`
                      : null,
                  });
                  setCorrection(blankCorrection);
                }, "Correction submitted to the selected reviewer.");
              }}
            >
              <Field label="Roster date">
                <input
                  className={input}
                  type="date"
                  value={rosterDate}
                  onChange={(e) => {
                    setRosterDate(e.target.value);
                    setCorrection(blankCorrection);
                  }}
                  max={today()}
                  required
                />
              </Field>
              <Field label="Employee deployment">
                <select
                  className={input}
                  value={correction.roster_id}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    const found = rosters.find((r) => r.id === id);
                    setCorrection({
                      ...correction,
                      roster_id: e.target.value,
                      version: found?.attendance_version || 0,
                    });
                  }}
                  required
                >
                  <option value="">Choose roster</option>
                  {rosters
                    .filter((r) => r.status !== "CANCELLED")
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name} · {r.site_name} · {r.shift_type}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label="Corrected status">
                <select
                  className={input}
                  value={correction.status}
                  onChange={(e) =>
                    setCorrection({ ...correction, status: e.target.value })
                  }
                >
                  {["present", "late", "absent", "leave"].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </Field>
              {["present", "late"].includes(correction.status) && (
                <>
                  <Field label="Check-in (India time)">
                    <input
                      className={input}
                      type="datetime-local"
                      required
                      value={correction.check_in_time}
                      onChange={(e) =>
                        setCorrection({
                          ...correction,
                          check_in_time: e.target.value,
                        })
                      }
                    />
                  </Field>
                  <Field label="Check-out (India time)">
                    <input
                      className={input}
                      type="datetime-local"
                      required
                      value={correction.check_out_time}
                      onChange={(e) =>
                        setCorrection({
                          ...correction,
                          check_out_time: e.target.value,
                        })
                      }
                    />
                  </Field>
                </>
              )}
              <Field label="Assigned reviewer">
                <select
                  className={input}
                  required
                  value={correction.assigned_to}
                  onChange={(e) =>
                    setCorrection({
                      ...correction,
                      assigned_to: e.target.value,
                    })
                  }
                >
                  <option value="">Select reviewer</option>
                  {options.approvers
                    .filter((a) => owner || a.id !== user.id)
                    .map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.name}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label="Reason for correction">
                <textarea
                  className={input}
                  value={correction.reason}
                  onChange={(e) =>
                    setCorrection({ ...correction, reason: e.target.value })
                  }
                  minLength={3}
                  maxLength={1000}
                  required
                />
              </Field>
              <button className={button} disabled={busy}>
                Submit correction
              </button>
            </form>
          )}
          <div className="space-y-3">
            {requests.map((r) => (
              <div
                key={r.id}
                className="rounded-xl border border-slate-200 bg-white p-4"
              >
                <div className="flex flex-wrap justify-between gap-2">
                  <h3 className="font-semibold">
                    {r.name} · {r.date} · {r.site_name}
                  </h3>
                  <span className="text-sm text-slate-500">{r.status}</span>
                </div>
                <p className="mt-2 text-sm">
                  {r.reason} · Proposed: {r.proposed.status} ·{" "}
                  {clock(r.proposed.check_in_time)} →{" "}
                  {clock(r.proposed.check_out_time)}
                </p>
                {r.remarks && (
                  <p className="mt-1 text-sm text-slate-500">
                    Decision: {r.remarks}
                  </p>
                )}
                {r.status === "PENDING" &&
                  can("attendance.approve") &&
                  (owner ||
                    (r.assigned_to === user.id &&
                      r.submitted_by !== user.id)) && (
                    <CorrectionDecision
                      busy={busy}
                      onDecision={(decision, remarks) =>
                        act(
                          () =>
                            api.post(
                              `/erp/attendance/corrections/${r.id}/decision`,
                              { decision, reason: remarks },
                            ),
                          `Correction ${decision === "APPROVE" ? "approved" : "rejected"}.`,
                        )
                      }
                    />
                  )}
              </div>
            ))}
            {!requests.length && (
              <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
                No correction requests.
              </p>
            )}
          </div>
        </>
      )}
      {tab === "rules" && owner && (
        <>
          <p className="mb-4 text-sm text-slate-500">
            Set each site's actual start time, regular duty hours and grace
            period before employees punch. Overnight shifts remain linked to
            their starting roster date. Changes apply to new check-ins.
          </p>
          <form
            className="grid gap-3 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                const { data } = await api.put("/erp/attendance/rules", {
                  ...rule,
                  site_id: Number(rule.site_id),
                  duty_hours: Number(rule.duty_hours),
                  grace_minutes: Number(rule.grace_minutes),
                });
                setRule({ ...rule, version: data.version, reason: "" });
              }, "Shift rule saved.");
            }}
          >
            <Field label="Site">
              <select
                className={input}
                value={rule.site_id}
                onChange={(e) => chooseRule(e.target.value, rule.shift_type)}
                required
              >
                <option value="">Choose site</option>
                {options.sites.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.site_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Shift">
              <select
                className={input}
                value={rule.shift_type}
                onChange={(e) => chooseRule(rule.site_id, e.target.value)}
              >
                {["DAY", "NIGHT", "GENERAL"].map((s) => (
                  <option key={s}>{s}</option>
                ))}
              </select>
            </Field>
            <Field label="Start time (India)">
              <input
                className={input}
                type="time"
                required
                value={rule.start_time}
                onChange={(e) =>
                  setRule({ ...rule, start_time: e.target.value })
                }
              />
            </Field>
            <Field label="Regular duty hours">
              <input
                className={input}
                type="number"
                min="0.5"
                max="16"
                step="0.5"
                required
                value={rule.duty_hours}
                onChange={(e) =>
                  setRule({ ...rule, duty_hours: e.target.value })
                }
              />
            </Field>
            <Field label="Grace minutes">
              <input
                className={input}
                type="number"
                min="0"
                max="120"
                required
                value={rule.grace_minutes}
                onChange={(e) =>
                  setRule({ ...rule, grace_minutes: e.target.value })
                }
              />
            </Field>
            <Field label="Reason">
              <input
                className={input}
                minLength={3}
                maxLength={1000}
                required
                value={rule.reason}
                onChange={(e) => setRule({ ...rule, reason: e.target.value })}
              />
            </Field>
            <button className={button} disabled={busy}>
              Save shift rule
            </button>
          </form>
          <div className="mt-4 space-y-2">
            {options.rules.map((r) => (
              <button
                key={`${r.site_id}-${r.shift_type}`}
                className="block w-full rounded-xl border border-slate-200 bg-white p-4 text-left text-sm"
                onClick={() => chooseRule(String(r.site_id), r.shift_type)}
              >
                {options.sites.find((s) => s.id === r.site_id)?.site_name} ·{" "}
                {r.shift_type} · {r.start_time} · {r.duty_hours}h +{" "}
                {r.grace_minutes} minute grace
              </button>
            ))}
          </div>
        </>
      )}
      {tab === "access" && owner && (
        <>
          <p className="mb-4 text-sm text-slate-500">
            Employees sign in with their phone and an 8–12 digit PIN. The first
            accepted punch binds their device. PIN and device resets revoke
            existing employee sessions.
          </p>
          <form
            className="grid gap-3 rounded-xl border border-slate-200 bg-white p-5 sm:grid-cols-3"
            onSubmit={(e) => {
              e.preventDefault();
              act(async () => {
                await api.post(
                  `/erp/attendance/employees/${access.employee_id}/access`,
                  { pin: access.pin, reason: access.reason },
                );
                setAccess({ ...access, pin: "", reason: "" });
              }, "Employee PIN saved.");
            }}
          >
            <Field label="Active employee">
              <select
                className={input}
                required
                value={access.employee_id}
                onChange={(e) =>
                  setAccess({
                    ...access,
                    employee_id: e.target.value,
                    pin: "",
                    reason: "",
                  })
                }
              >
                <option value="">Choose employee</option>
                {options.employees.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.name} · {e.employee_code} ·{" "}
                    {e.access_enabled ? "PIN enabled" : "No PIN"} ·{" "}
                    {e.device_bound ? "Device bound" : "No device"}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="New employee PIN">
              <input
                className={input}
                type="password"
                inputMode="numeric"
                autoComplete="new-password"
                pattern="[0-9]{8,12}"
                minLength={8}
                maxLength={12}
                value={access.pin}
                onChange={(e) => setAccess({ ...access, pin: e.target.value })}
                required
              />
            </Field>
            <Field label="Reason">
              <input
                className={input}
                minLength={3}
                maxLength={1000}
                value={access.reason}
                onChange={(e) =>
                  setAccess({ ...access, reason: e.target.value })
                }
                required
              />
            </Field>
            <button className={button} disabled={busy}>
              Save / reset PIN
            </button>
            <button
              type="button"
              disabled={
                busy || !access.employee_id || access.reason.trim().length < 3
              }
              className="rounded-lg border border-amber-300 px-4 py-2 text-sm text-amber-800 disabled:opacity-50"
              onClick={() =>
                act(
                  () =>
                    api.post(
                      `/erp/attendance/employees/${access.employee_id}/reset-device`,
                      { reason: access.reason },
                    ),
                  "Device reset; employee must sign in again.",
                )
              }
            >
              Reset registered device
            </button>
          </form>
        </>
      )}
    </MainLayout>
  );
}
function CorrectionDecision({ busy, onDecision }) {
  const [remarks, setRemarks] = useState("");
  return (
    <form
      className="mt-3 flex flex-wrap gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        onDecision("APPROVE", remarks);
      }}
    >
      <input
        className={`${input} max-w-md`}
        aria-label="Correction decision remarks"
        placeholder="Decision remarks"
        minLength={3}
        maxLength={1000}
        required
        value={remarks}
        onChange={(e) => setRemarks(e.target.value)}
      />
      <button className={button} disabled={busy}>
        Approve correction
      </button>
      <button
        type="button"
        className="rounded-lg border border-red-200 px-4 text-sm text-red-700 disabled:opacity-50"
        disabled={busy || remarks.trim().length < 3}
        onClick={() => onDecision("REJECT", remarks)}
      >
        Reject
      </button>
    </form>
  );
}
