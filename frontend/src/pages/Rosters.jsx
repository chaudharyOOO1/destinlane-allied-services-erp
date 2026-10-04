import { useCallback, useEffect, useState } from "react";
import MainLayout from "../layouts/MainLayout";
import api from "../api/axios";
import { useAccess } from "../context/AccessContext";
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
const empty = () => ({
  site_id: "",
  guard_id: "",
  date: today(),
  shift_type: "DAY",
  notes: "",
});
const errorText = (e) =>
  typeof e.response?.data?.detail === "string"
    ? e.response.data.detail
    : "Check the schedule details and retry.";
export default function Rosters() {
  const { can } = useAccess();
  const [rows, setRows] = useState([]),
    [sites, setSites] = useState([]),
    [people, setPeople] = useState([]),
    [shortfall, setShortfall] = useState([]),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [form, setForm] = useState(empty),
    [selected, setSelected] = useState(null),
    [reason, setReason] = useState(""),
    [history, setHistory] = useState([]),
    [repeat, setRepeat] = useState(false),
    [end, setEnd] = useState(today()),
    [weekdays, setWeekdays] = useState([0, 1, 2, 3, 4, 5, 6]),
    [filters, setFilters] = useState({
      start: "",
      end: "",
      status: "",
      site_id: "",
    }),
    [analysisDate, setAnalysisDate] = useState(today());
  const load = useCallback(async () => {
    const [r, o, s] = await Promise.all([
      api.get("/erp/rosters"),
      api.get("/erp/rosters/options"),
      api.get("/erp/rosters/shortfall-analysis", {
        params: { analysis_date: analysisDate },
      }),
    ]);
    setRows(r.data);
    setSites(o.data.sites);
    setShortfall(s.data);
    setLoading(false);
  }, [analysisDate]);
  useEffect(() => {
    let live = true;
    load().catch((e) => {
      if (live) {
        setError(errorText(e));
        setLoading(false);
      }
    });
    return () => {
      live = false;
    };
  }, [load]);
  useEffect(() => {
    let live = true;
    setPeople([]);
    api
      .get("/erp/rosters/employees", {
        params: {
          assignment_date: form.date,
          exclude_roster_id: selected?.id || 0,
          ...(form.site_id ? { site_id: form.site_id } : {}),
        },
      })
      .then((r) => {
        if (live) setPeople(r.data);
      })
      .catch((e) => {
        if (live) setError(errorText(e));
      });
    return () => {
      live = false;
    };
  }, [form.date, form.site_id, selected?.id]);
  const run = async (fn) => {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const reset = () => {
    setSelected(null);
    setForm(empty());
    setReason("");
    setHistory([]);
    setRepeat(false);
  };
  const save = (e) => {
    e.preventDefault();
    run(async () => {
      const data = {
        ...form,
        site_id: Number(form.site_id),
        guard_id: Number(form.guard_id),
      };
      if (selected)
        await api.patch(`/erp/rosters/${selected.id}`, {
          ...data,
          version: selected.version,
          reason,
        });
      else if (repeat) {
        const { date, ...rest } = data;
        await api.post("/erp/rosters/repeat", {
          ...rest,
          start: date,
          end,
          weekdays,
        });
      } else await api.post("/erp/rosters", data);
      reset();
      await load();
      setMessage("Deployment schedule saved.");
    });
  };
  const filtered = rows.filter(
    (r) =>
      (!filters.start || r.date >= filters.start) &&
      (!filters.end || r.date <= filters.end) &&
      (!filters.status || r.status === filters.status) &&
      (!filters.site_id || String(r.site_id) === filters.site_id),
  );
  const selectedPerson =
    selected && !people.some((p) => p.guard_id === selected.guard_id)
      ? [
          {
            guard_id: selected.guard_id,
            name: selected.name,
            employee_code: selected.employee_code,
          },
        ]
      : [];
  return (
    <MainLayout>
      <div className="space-y-5">
        <header className="flex flex-wrap justify-between gap-3">
          <div>
            <h1 className="text-3xl font-semibold">Rosters & Deployment</h1>
            <p className="mt-2 text-sm text-slate-500">
              Assign approved employees to client sites. One active assignment
              per employee per day.
            </p>
          </div>
          <button className={button} disabled={busy} onClick={() => run(load)}>
            Refresh
          </button>
        </header>
        {error && (
          <p
            role="alert"
            className="rounded-lg bg-red-50 p-3 text-sm text-red-700"
          >
            {error}
          </p>
        )}
        {message && (
          <p
            role="status"
            className="rounded-lg bg-green-50 p-3 text-sm text-green-800"
          >
            {message}
          </p>
        )}
        {(selected ? can("rosters.edit") : can("rosters.create")) && (
          <section className="rounded-xl border bg-white p-5">
            <h2 className="font-semibold">
              {selected
                ? `Edit deployment #${selected.id}`
                : "Schedule deployment"}
            </h2>
            <p className="mt-2 text-xs text-slate-500">
              The employee must match the client and branch, have approved
              joining and valid compliance on every scheduled date. Linked
              contracts must cover deployment.
            </p>
            <form onSubmit={save} className="mt-4">
              <fieldset
                disabled={busy}
                className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
              >
                <label className="text-xs">
                  Client site
                  <select
                    required
                    className={input}
                    value={form.site_id}
                    onChange={(e) =>
                      setForm((p) => ({
                        ...p,
                        site_id: e.target.value,
                        guard_id: "",
                      }))
                    }
                  >
                    <option value="">Select site</option>
                    {sites.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.site_name} · {s.client_name} ·{" "}
                        {s.branch || "Head office"}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs">
                  Date
                  <input
                    required
                    type="date"
                    min={today()}
                    className={input}
                    value={form.date}
                    onChange={(e) =>
                      setForm((p) => ({
                        ...p,
                        date: e.target.value,
                        guard_id: "",
                      }))
                    }
                  />
                </label>
                <label className="text-xs">
                  Available employee
                  <select
                    required
                    className={input}
                    value={form.guard_id}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, guard_id: e.target.value }))
                    }
                  >
                    <option value="">Select employee</option>
                    {[...selectedPerson, ...people].map((p) => (
                      <option key={p.guard_id} value={p.guard_id}>
                        {p.employee_code} · {p.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-xs">
                  Shift
                  <select
                    className={input}
                    value={form.shift_type}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, shift_type: e.target.value }))
                    }
                  >
                    {["DAY", "NIGHT", "GENERAL"].map((s) => (
                      <option key={s}>{s}</option>
                    ))}
                  </select>
                </label>
                <label className="text-xs">
                  Notes
                  <textarea
                    className={input}
                    maxLength={2000}
                    value={form.notes}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, notes: e.target.value }))
                    }
                  />
                </label>
                {selected ? (
                  <label className="text-xs">
                    Required change reason
                    <input
                      required
                      minLength={3}
                      className={input}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                  </label>
                ) : (
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={repeat}
                      onChange={(e) => setRepeat(e.target.checked)}
                    />
                    Repeat on selected weekdays
                  </label>
                )}
                {repeat && !selected && (
                  <>
                    <label className="text-xs">
                      Through date (up to 31 days)
                      <input
                        required
                        type="date"
                        min={form.date}
                        className={input}
                        value={end}
                        onChange={(e) => setEnd(e.target.value)}
                      />
                    </label>
                    <div className="flex flex-wrap gap-3 sm:col-span-2">
                      {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map(
                        (d, i) => (
                          <label key={d} className="text-sm">
                            <input
                              type="checkbox"
                              checked={weekdays.includes(i)}
                              onChange={(e) =>
                                setWeekdays((p) =>
                                  e.target.checked
                                    ? [...p, i]
                                    : p.filter((x) => x !== i),
                                )
                              }
                            />{" "}
                            {d}
                          </label>
                        ),
                      )}
                    </div>
                  </>
                )}
              </fieldset>
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  className={button}
                  disabled={
                    busy ||
                    !sites.length ||
                    !form.guard_id ||
                    (repeat && !weekdays.length)
                  }
                >
                  {selected
                    ? "Save change"
                    : repeat
                      ? "Schedule date range"
                      : "Schedule employee"}
                </button>
                {selected && (
                  <button
                    type="button"
                    className={button}
                    disabled={busy}
                    onClick={reset}
                  >
                    Exit editing
                  </button>
                )}
              </div>
            </form>
            {!sites.length && (
              <p className="mt-3 text-sm text-amber-700">
                Create an active client site before scheduling. Real-data setup
                can be completed later.
              </p>
            )}
            {sites.length > 0 && !people.length && (
              <p className="mt-3 text-sm text-slate-500">
                No available employees match this site and date. Check joining
                approval, allocation, existing rosters and compliance expiry.
              </p>
            )}
          </section>
        )}
        <section className="rounded-xl border bg-white p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="font-semibold">Staffing coverage</h2>
            <label className="text-xs">
              Analysis date
              <input
                aria-label="Coverage date"
                type="date"
                className={input}
                value={analysisDate}
                onChange={(e) => setAnalysisDate(e.target.value)}
              />
            </label>
          </div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {shortfall
              .filter((x) => x.required || x.active || x.blocked_assignments)
              .map((s) => (
                <div
                  key={s.site_id + s.shift_type}
                  className={`rounded-lg border p-3 text-sm ${s.vacancy || s.blocked_assignments ? "border-amber-200 bg-amber-50" : "bg-slate-50"}`}
                >
                  <strong>
                    {s.site_name} · {s.shift_type}
                  </strong>
                  <p className="mt-2">
                    Required {s.required} · Deployable {s.active} · Vacancy{" "}
                    {s.vacancy}
                  </p>
                  {s.surplus > 0 && <p className="mt-1">Surplus {s.surplus}</p>}
                  {s.blocked_assignments > 0 && (
                    <p className="mt-1 text-red-700">
                      Blocked assignments: {s.blocked_assignments}
                    </p>
                  )}{" "}
                  {can("rosters.create") && s.vacancy > 0 && (
                    <button
                      className="mt-2 font-semibold text-teal-700"
                      disabled={busy}
                      onClick={() => {
                        reset();
                        setForm({
                          ...empty(),
                          site_id: String(s.site_id),
                          date: analysisDate,
                          shift_type: s.shift_type,
                        });
                      }}
                    >
                      Fill vacancy
                    </button>
                  )}
                </div>
              ))}
          </div>
          {!shortfall.some(
            (x) => x.required || x.active || x.blocked_assignments,
          ) && (
            <p className="mt-3 text-sm text-slate-500">
              Configure site staffing requirements to track day, night and
              general shift coverage.
            </p>
          )}
        </section>
        <section className="rounded-xl border bg-white p-5">
          <h2 className="font-semibold">Deployment register</h2>
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            <label className="text-xs">
              From
              <input
                type="date"
                className={input}
                value={filters.start}
                onChange={(e) =>
                  setFilters((p) => ({ ...p, start: e.target.value }))
                }
              />
            </label>
            <label className="text-xs">
              To
              <input
                type="date"
                className={input}
                value={filters.end}
                onChange={(e) =>
                  setFilters((p) => ({ ...p, end: e.target.value }))
                }
              />
            </label>
            <select
              aria-label="Site filter"
              className={input}
              value={filters.site_id}
              onChange={(e) =>
                setFilters((p) => ({ ...p, site_id: e.target.value }))
              }
            >
              <option value="">All sites</option>
              {sites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.site_name}
                </option>
              ))}
            </select>
            <select
              aria-label="Status filter"
              className={input}
              value={filters.status}
              onChange={(e) =>
                setFilters((p) => ({ ...p, status: e.target.value }))
              }
            >
              <option value="">All statuses</option>
              {["SCHEDULED", "COMPLETED", "CANCELLED"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </div>
          <div className="mt-4 overflow-auto">
            <table className="w-full min-w-[850px] text-left text-sm">
              <thead className="bg-slate-50">
                <tr>
                  {[
                    "Employee",
                    "Client / site",
                    "Branch",
                    "Date / shift",
                    "Status",
                    "Actions",
                  ].map((x) => (
                    <th key={x} className="p-3">
                      {x}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((r) => (
                  <tr key={r.id} className="border-b">
                    <td className="p-3 font-medium">
                      {r.name}
                      <p className="text-xs text-slate-500">
                        {r.employee_code}
                      </p>
                    </td>
                    <td className="p-3">
                      {r.site_name}
                      <p className="text-xs text-slate-500">{r.client_name}</p>
                    </td>
                    <td className="p-3">{r.branch || "—"}</td>
                    <td className="p-3">
                      {r.date}
                      <p className="text-xs text-slate-500">{r.shift_type}</p>
                    </td>
                    <td className="p-3 text-xs">{r.status}</td>
                    <td className="p-3">
                      <div className="flex gap-3">
                        {r.status === "SCHEDULED" && can("rosters.edit") && (
                          <>
                            <button
                              disabled={busy}
                              className="text-teal-700"
                              onClick={() => {
                                setSelected(r);
                                setRepeat(false);
                                setReason("");
                                setForm({
                                  site_id: String(r.site_id),
                                  guard_id: String(r.guard_id),
                                  date: r.date,
                                  shift_type: r.shift_type,
                                  notes: r.notes || "",
                                });
                              }}
                            >
                              Edit
                            </button>
                            <button
                              disabled={busy}
                              className="text-red-700"
                              onClick={() => {
                                const reason = window.prompt(
                                  "Reason for cancelling this assignment",
                                );
                                if (reason)
                                  run(async () => {
                                    await api.post(
                                      `/erp/rosters/${r.id}/cancel`,
                                      { version: r.version, reason },
                                    );
                                    reset();
                                    await load();
                                    setMessage(
                                      "Assignment cancelled and retained in history.",
                                    );
                                  });
                              }}
                            >
                              Cancel
                            </button>
                          </>
                        )}
                        <button
                          disabled={busy}
                          onClick={() =>
                            run(async () => {
                              const { data } = await api.get(
                                `/erp/rosters/${r.id}/history`,
                              );
                              setHistory(data);
                            })
                          }
                        >
                          History
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {loading ? (
              <p className="p-8 text-center text-sm text-slate-500">
                Loading deployments…
              </p>
            ) : (
              !filtered.length && (
                <p className="p-8 text-center text-sm text-slate-500">
                  No matching assignments.
                </p>
              )
            )}
          </div>
        </section>
        {history.length > 0 && (
          <section className="rounded-xl border bg-white p-5">
            <h2 className="font-semibold">Deployment change history</h2>
            {history.map((h) => (
              <p key={h.id} className="mt-3 text-sm">
                #{h.roster_id} · {h.action} ·{" "}
                {new Date(h.created_at).toLocaleString()} ·{" "}
                {h.changed_by_name || "System"} ·{" "}
                {h.details?.reason || "Scheduled"}
              </p>
            ))}
          </section>
        )}
      </div>
    </MainLayout>
  );
}
