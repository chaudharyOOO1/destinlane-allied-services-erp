import { useCallback, useEffect, useState } from "react";
import MainLayout from "../layouts/MainLayout";
import api from "../api/axios";
import { useAccess } from "../context/AccessContext";
import { useAuth } from "../context/AuthContext";

const tabs = [
  ["master", "Employee Master"],
  ["creation", "Employee Creation"],
  ["compliance", "Employee Compliance Documents"],
  ["reports", "Employee Reports"],
];
const inputClass =
  "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm";
const buttonClass =
  "rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50";
const types = [
  "PHOTO",
  "AADHAAR",
  "PAN",
  "FORM_11",
  "ESIC_FORM",
  "BANK_PASSBOOK",
  "POLICE_VERIFICATION",
  "MEDICAL_FITNESS",
  "FORM_11A",
  "BANK_CHEQUE",
  "ADDRESS_PROOF",
  "PSARA_CERTIFICATE",
  "GUN_LICENSE",
  "NOMINEE_ID",
  "OTHER",
];
const categories = [
  "GUARD",
  "GUNMAN",
  "SUPERVISOR",
  "FIELD_OFFICER",
  "JANITOR",
  "CLEANER",
  "FACILITY_ATTENDANT",
  "GDA",
  "NURSE_ASSISTANT",
  "HOSPITAL_ATTENDANT",
];
const intake = [
  "name",
  "father_name",
  "aadhaar_no",
  "phone",
  "client_id",
  "branch",
];
const groups = [
  [
    "Personal information",
    [
      "name",
      "father_name",
      "phone",
      "dob",
      "gender",
      "marital_status",
      "aadhaar_no",
      "pan_no",
      "permanent_address",
      "present_address",
    ],
  ],
  [
    "Employment",
    [
      "designation",
      "client_id",
      "branch",
      "site_id",
      "joining_date",
      "vertical",
      "category",
      "uan",
      "esic_number",
    ],
  ],
  [
    "Emergency contact",
    ["emergency_name", "emergency_contact", "emergency_relation"],
  ],
  [
    "Bank details",
    ["bank_account_no", "bank_ifsc", "bank_name", "bank_branch"],
  ],
  [
    "Nominee",
    [
      "nominee_name",
      "nominee_relation",
      "nominee_dob",
      "nominee_aadhaar",
      "nominee_percentage",
    ],
  ],
  [
    "Gunman information",
    [
      "gun_license_no",
      "arms_issuing_authority",
      "gun_license_expiry",
      "arms_caliber",
      "weapon_serial_no",
      "ammunition_count",
      "jurisdiction_limits",
    ],
  ],
  [
    "Uniform issue",
    [
      "uniform_shirt",
      "uniform_trousers",
      "uniform_shoes",
      "uniform_belt",
      "uniform_cap",
      "uniform_issue_date",
      "uniform_total_cost",
      "uniform_monthly_emi",
    ],
  ],
  ["Additional notes", ["notes"]],
];
const labels = {
  name: "Employee name",
  father_name: "Father’s name",
  aadhaar_no: "Aadhaar number",
  client_id: "Client",
  branch: "Company branch",
  site_id: "Client site",
  bank_ifsc: "IFSC",
  bank_account_no: "Bank account number",
  bank_branch: "Bank branch",
  dob: "Date of birth",
  uan: "UAN",
  esic_number: "ESIC number",
  vertical: "Service vertical",
};
const label = (key) =>
  labels[key] || key.replaceAll("_", " ").replace(/^./, (x) => x.toUpperCase());
const errorText = (e) => {
  const d = e.response?.data?.detail;
  if (typeof d === "string") return d;
  if (d?.missing_fields)
    return `Complete: ${d.missing_fields.join(", ") || "all details"}. Required documents: ${d.missing_documents.join(", ") || "none"}.`;
  return "Unable to complete the request. Check the details and retry.";
};

function Field({
  name,
  value,
  onChange,
  options,
  profile = {},
  required = false,
}) {
  let choices = null;
  if (name === "client_id")
    choices = options.clients.map((x) => [x.id, x.company_name]);
  if (name === "site_id")
    choices = options.sites
      .filter(
        (x) =>
          String(x.client_id) === String(profile.client_id) &&
          (!x.branch || x.branch === profile.branch),
      )
      .map((x) => [x.id, x.site_name]);
  if (name === "branch")
    choices = options.branches.map((x) => [x.code, x.name]);
  if (name === "gender")
    choices = ["MALE", "FEMALE", "OTHER"].map((x) => [x, x]);
  if (name === "category")
    choices = categories.map((x) => [x, x.replaceAll("_", " ")]);
  if (name === "vertical")
    choices = ["SECURITY", "HOUSEKEEPING", "NURSING"].map((x) => [x, x]);
  if (name === "marital_status")
    choices = ["SINGLE", "MARRIED", "WIDOWED", "DIVORCED"].map((x) => [x, x]);
  const checkbox =
    name.startsWith("uniform_") &&
    ![
      "uniform_issue_date",
      "uniform_total_cost",
      "uniform_monthly_emi",
    ].includes(name);
  const date =
    name === "dob" ||
    name.endsWith("_date") ||
    name.endsWith("_expiry") ||
    name === "nominee_dob";
  return (
    <label className="block text-xs font-medium text-slate-600">
      <span className="mb-1 block">
        {label(name)}
        {required ? " *" : ""}
      </span>
      {choices ? (
        <select
          required={required}
          className={inputClass}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">Select</option>
          {choices.map(([id, title]) => (
            <option key={id} value={id}>
              {title}
            </option>
          ))}
        </select>
      ) : checkbox ? (
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(e) => onChange(e.target.checked)}
        />
      ) : name.includes("address") || name === "notes" ? (
        <textarea
          className={inputClass}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      ) : (
        <input
          required={required}
          className={inputClass}
          type={date ? "date" : "text"}
          inputMode={
            name.includes("aadhaar") ||
            name === "phone" ||
            name === "bank_account_no"
              ? "numeric"
              : undefined
          }
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </label>
  );
}

export default function Employees() {
  const { can } = useAccess();
  const { user } = useAuth();
  const [tab, setTab] = useState("master");
  const [rows, setRows] = useState([]);
  const [options, setOptions] = useState({
    clients: [],
    sites: [],
    branches: [],
    approvers: [],
  });
  const [approvals, setApprovals] = useState([]);
  const [rules, setRules] = useState([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    q: "",
    status: "",
    branch: "",
    site_id: "",
    designation: "",
  });
  const [intimation, setIntimation] = useState({});
  const [record, setRecord] = useState(null);
  const [form, setForm] = useState({});
  const [dirty, setDirty] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [history, setHistory] = useState([]);
  const [docForm, setDocForm] = useState({
    document_type: "PHOTO",
    issue_date: "",
    expiry_date: "",
    document_number: "",
    issuing_authority: "",
  });
  const [file, setFile] = useState(null);
  const [fileKey, setFileKey] = useState(0);
  const [remarks, setRemarks] = useState("");
  const [stateForm, setStateForm] = useState({
    status: "INACTIVE",
    reason: "",
  });
  const [report, setReport] = useState({
    kind: "master",
    start: "",
    end: "",
    days: 60,
  });
  const [reportRows, setReportRows] = useState([]);
  const [reportLoaded, setReportLoaded] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [code, setCode] = useState("");
  const load = useCallback(async () => {
    const [directory, lookups, inbox, categories, compliance] =
      await Promise.all([
        api.get("/erp/employees"),
        api.get("/erp/employees/options"),
        api.get("/erp/employees/workflow/approvals"),
        api.get("/erp/employees/workflow/approval-categories"),
        api.get("/erp/employees/compliance"),
      ]);
    setRows(directory.data);
    setOptions(lookups.data);
    setApprovals(inbox.data);
    setRules(categories.data);
    setAlerts(compliance.data);
    setLoading(false);
  }, []);
  useEffect(() => {
    load().catch((e) => {
      setError(errorText(e));
      setLoading(false);
    });
  }, [load]);
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
  const openRecord = async (id) => {
    const [r, docs, h] = await Promise.all([
      api.get(`/erp/employees/workflow/joining/${id}`),
      api.get(`/erp/employees/${id}/documents`),
      api.get(`/erp/employees/${id}/history`),
    ]);
    setRecord(r.data);
    setForm(r.data.profile);
    setDocuments(docs.data);
    setHistory(h.data);
    setDirty(false);
    setRemarks("");
    setFile(null);
    setFileKey((k) => k + 1);
  };
  const editable =
    record &&
    ["DRAFT", "REJECTED"].includes(record.joining_status) &&
    can("employees.edit");
  const submittedApproval = approvals.find((x) => x.employee_id === record?.id);
  const update = (key, value) => {
    setForm((p) => ({
      ...p,
      [key]: value,
      ...(["client_id", "branch"].includes(key) ? { site_id: null } : {}),
    }));
    setDirty(true);
  };
  const params = () =>
    Object.fromEntries(
      Object.entries({ ...filters, ...report }).filter(([, v]) => v !== ""),
    );
  const filtered = rows.filter(
    (r) =>
      (!filters.status || r.status.toUpperCase() === filters.status) &&
      (!filters.branch || r.branch === filters.branch) &&
      (!filters.site_id || String(r.site_id) === filters.site_id) &&
      (!filters.designation || r.designation === filters.designation) &&
      (!filters.q ||
        [r.name, r.employee_code, r.phone].some((v) =>
          String(v || "")
            .toLowerCase()
            .includes(filters.q.toLowerCase()),
        )),
  );
  const save = () =>
    run(async () => {
      await api.patch(`/erp/employees/workflow/joining/${record.id}`, {
        version: record.version,
        profile: form,
      });
      await openRecord(record.id);
      await load();
      setMessage("Employee draft saved. Continue this file anytime.");
    });
  const submit = () =>
    run(async () => {
      await api.post(`/erp/employees/workflow/joining/${record.id}/submit`, {
        version: record.version,
      });
      await openRecord(record.id);
      await load();
      setMessage(
        user.role === "OWNER"
          ? "Employee approved and activated."
          : "Employee file sent to the assigned approver.",
      );
    });
  const decision = (decision) =>
    run(async () => {
      await api.post(
        `/erp/employees/workflow/approvals/${submittedApproval.id}/decision`,
        { decision, remarks },
      );
      await openRecord(record.id);
      await load();
      setMessage(
        decision === "REJECT"
          ? "File returned with remarks. The employee ID is retained."
          : "Approval recorded.",
      );
    });
  const download = (format) =>
    run(async () => {
      const r = await api.get("/erp/employees/reports/export", {
        params: { ...params(), format },
        responseType: "blob",
      });
      const url = URL.createObjectURL(r.data);
      const a = document.createElement("a");
      a.href = url;
      a.download = `employee-${report.kind}.${format}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  const refreshDocs = async () => {
    await openRecord(record.id);
    await load();
  };
  return (
    <MainLayout>
      <div className="space-y-5">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-wider text-slate-500">
              Deployed workforce
            </p>
            <h1 className="mt-1 text-3xl font-semibold">Employee Management</h1>
            <p className="mt-2 text-sm text-slate-500">
              Intimation → Joining bucket → Complete employee file → Assigned
              approval
            </p>
          </div>
          <button
            className={buttonClass}
            disabled={busy}
            onClick={() => run(load)}
          >
            Refresh
          </button>
        </header>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {[
            ["All employees", rows.length],
            [
              "Active",
              rows.filter((r) => r.status.toUpperCase() === "ACTIVE").length,
            ],
            [
              "Joining / approval",
              rows.filter((r) =>
                ["DRAFT", "PENDING_APPROVAL", "REJECTED"].includes(
                  r.status.toUpperCase(),
                ),
              ).length,
            ],
            [
              "Bench",
              rows.filter((r) => r.status.toUpperCase() === "BENCH").length,
            ],
          ].map(([title, count]) => (
            <div key={title} className="rounded-xl border bg-white p-4">
              <p className="text-xs text-slate-500">{title}</p>
              <p className="mt-1 text-2xl font-semibold">{count}</p>
            </div>
          ))}
        </div>
        <nav className="flex flex-wrap gap-2" aria-label="Employee sections">
          {tabs.map(([key, title]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={
                tab === key
                  ? buttonClass
                  : "rounded-lg border bg-white px-4 py-2 text-sm"
              }
            >
              {title}
            </button>
          ))}
        </nav>
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
        {(tab === "master" || tab === "reports") && (
          <div className="grid gap-3 rounded-xl border bg-white p-4 sm:grid-cols-2 lg:grid-cols-5">
            <input
              aria-label="Search employee"
              className={inputClass}
              placeholder="Search name, ID or phone"
              value={filters.q}
              onChange={(e) => setFilters((p) => ({ ...p, q: e.target.value }))}
            />
            <select
              aria-label="Status filter"
              className={inputClass}
              value={filters.status}
              onChange={(e) =>
                setFilters((p) => ({ ...p, status: e.target.value }))
              }
            >
              <option value="">All statuses</option>
              {[
                "DRAFT",
                "PENDING_APPROVAL",
                "REJECTED",
                "ACTIVE",
                "BENCH",
                "INACTIVE",
                "TERMINATED",
              ].map((x) => (
                <option key={x}>{x}</option>
              ))}
            </select>
            <select
              aria-label="Branch filter"
              className={inputClass}
              value={filters.branch}
              onChange={(e) =>
                setFilters((p) => ({
                  ...p,
                  branch: e.target.value,
                  site_id: "",
                }))
              }
            >
              <option value="">All branches</option>
              {options.branches.map((x) => (
                <option key={x.code} value={x.code}>
                  {x.name}
                </option>
              ))}
            </select>
            <select
              aria-label="Site filter"
              className={inputClass}
              value={filters.site_id}
              onChange={(e) =>
                setFilters((p) => ({ ...p, site_id: e.target.value }))
              }
            >
              <option value="">All sites</option>
              {options.sites
                .filter((x) => !filters.branch || x.branch === filters.branch)
                .map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.site_name}
                  </option>
                ))}
            </select>
            <input
              aria-label="Designation filter"
              className={inputClass}
              placeholder="Designation (exact)"
              value={filters.designation}
              onChange={(e) =>
                setFilters((p) => ({ ...p, designation: e.target.value }))
              }
            />
          </div>
        )}
        {tab === "master" && (
          <>
            <EmployeeTable
              rows={filtered}
              loading={loading}
              onOpen={(id) => run(() => openRecord(id))}
            />
            <div className="flex flex-wrap gap-2 rounded-xl border bg-white p-4">
              <input
                aria-label="Employee code authenticity check"
                className={inputClass + " max-w-xs"}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="E-DAS-0070"
              />
              <button
                className={buttonClass}
                disabled={busy || !code}
                onClick={() =>
                  run(async () => {
                    const { data } = await api.get(
                      "/erp/employees/code-check",
                      { params: { code } },
                    );
                    setMessage(
                      data.registered
                        ? `Registered: ${data.employee.employee_code} — ${data.employee.name}`
                        : data.valid_format
                          ? "Correct format, but this ID is not registered."
                          : "Invalid employee ID format.",
                    );
                  })
                }
              >
                Check ID
              </button>
            </div>
          </>
        )}
        {tab === "creation" && (
          <>
            <section className="rounded-xl border bg-white p-5">
              <h2 className="text-lg font-semibold">Employee intimation</h2>
              <p className="mt-1 text-sm text-slate-500">
                Submitting these six details issues a permanent employee ID and
                adds the file to the joining bucket. Collect the physical file,
                then complete the details anytime.
              </p>
              {(!options.clients.length || !options.branches.length) && (
                <p className="mt-3 text-sm text-amber-700">
                  Add an active client and company branch before submitting
                  intimation.
                </p>
              )}
              {can("employees.create") && (
                <form
                  className="mt-4"
                  onSubmit={(e) => {
                    e.preventDefault();
                    run(async () => {
                      const { data } = await api.post(
                        "/erp/employees/workflow/intimations",
                        intimation,
                      );
                      setIntimation({});
                      await load();
                      await openRecord(data.id);
                      setMessage(
                        `Intimation submitted. Permanent employee ID: ${data.employee_code}`,
                      );
                    });
                  }}
                >
                  <fieldset
                    disabled={busy}
                    className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
                  >
                    {intake.map((name) => (
                      <Field
                        key={name}
                        name={name}
                        value={intimation[name]}
                        options={options}
                        required
                        onChange={(value) =>
                          setIntimation((p) => ({ ...p, [name]: value }))
                        }
                      />
                    ))}
                  </fieldset>
                  <button
                    disabled={
                      busy ||
                      !options.clients.length ||
                      !options.branches.length
                    }
                    className={buttonClass + " mt-4"}
                  >
                    Submit intimation & generate employee ID
                  </button>
                </form>
              )}
            </section>
            <section>
              <h2 className="mb-3 text-lg font-semibold">Joining bucket</h2>
              <EmployeeTable
                rows={rows.filter((r) => r.joining_status !== "APPROVED")}
                loading={loading}
                onOpen={(id) => run(() => openRecord(id))}
              />
            </section>
            <section className="rounded-xl border bg-white p-5">
              <h2 className="text-lg font-semibold">
                Assigned joining approvals
              </h2>
              {!approvals.length ? (
                <p className="mt-3 text-sm text-slate-500">
                  No employee files awaiting your approval.
                </p>
              ) : (
                approvals.map((x) => (
                  <div
                    key={x.id}
                    className="mt-3 flex justify-between border-t pt-3 text-sm"
                  >
                    <span>
                      {x.employee_code} · {x.name}
                    </span>
                    <button
                      disabled={busy}
                      onClick={() => run(() => openRecord(x.employee_id))}
                      className="font-semibold text-teal-700"
                    >
                      Review file
                    </button>
                  </div>
                ))
              )}
            </section>
            {user.role === "OWNER" && (
              <section className="rounded-xl border bg-white p-5">
                <h2 className="text-lg font-semibold">
                  Joining approver setup
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  Assign each required step. The last assigned step must be
                  final. Submissions retain their assigned chain even if this
                  setup changes.
                </p>
                {rules.map((r) => (
                  <div
                    key={r.id}
                    className="mt-4 flex flex-wrap items-center gap-3"
                  >
                    <span className="min-w-40 text-sm">{r.category_name}</span>
                    <select
                      aria-label={`Approver for ${r.category_name}`}
                      className={inputClass + " max-w-xs"}
                      value={r.approver_user_id || ""}
                      onChange={(e) =>
                        setRules((p) =>
                          p.map((x) =>
                            x.id === r.id
                              ? {
                                  ...x,
                                  approver_user_id: e.target.value
                                    ? Number(e.target.value)
                                    : null,
                                }
                              : x,
                          ),
                        )
                      }
                    >
                      <option value="">Not assigned</option>
                      {options.approvers.map((x) => (
                        <option key={x.id} value={x.id}>
                          {x.name} · {x.role}
                        </option>
                      ))}
                    </select>
                    <label className="text-sm">
                      <input
                        type="checkbox"
                        checked={r.is_final_approver}
                        onChange={(e) =>
                          setRules((p) =>
                            p.map((x) =>
                              x.id === r.id
                                ? { ...x, is_final_approver: e.target.checked }
                                : e.target.checked
                                  ? { ...x, is_final_approver: false }
                                  : x,
                            ),
                          )
                        }
                      />{" "}
                      Final approver
                    </label>
                    <button
                      className={buttonClass}
                      disabled={busy}
                      onClick={() =>
                        run(async () => {
                          await api.put(
                            `/erp/employees/workflow/approval-categories/${r.id}`,
                            {
                              approver_user_id: r.approver_user_id,
                              is_final_approver: r.is_final_approver,
                            },
                          );
                          await load();
                          setMessage("Joining approval step saved.");
                        })
                      }
                    >
                      Save step
                    </button>
                  </div>
                ))}
              </section>
            )}
          </>
        )}
        {tab === "compliance" && (
          <section className="rounded-xl border bg-white p-5">
            <h2 className="text-lg font-semibold">
              Compliance alerts & document files
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Police verification warnings: 45 days. Gun licence: 60 days.
              Medical fitness: annual renewal. Missing or expired mandatory
              documents block deployment.
            </p>
            <select
              aria-label="Select employee document file"
              className={inputClass + " mt-4 max-w-xl"}
              value={record?.id || ""}
              onChange={(e) => {
                if (e.target.value) run(() => openRecord(e.target.value));
              }}
            >
              <option value="">
                Select an employee to upload or review documents
              </option>
              {rows.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.employee_code} · {r.name}
                </option>
              ))}
            </select>
            <div className="mt-4 space-y-3">
              {alerts.map((r) => (
                <div key={r.id} className="rounded-lg border p-3 text-sm">
                  <button
                    disabled={busy}
                    onClick={() => run(() => openRecord(r.id))}
                    className="font-semibold text-teal-700"
                  >
                    {r.employee_code} · {r.name}
                  </button>
                  <p className="mt-1 text-slate-600">
                    {r.joining_incomplete
                      ? "Joining approval incomplete. "
                      : ""}
                    {r.compliance_missing.length
                      ? `Missing / expired: ${r.compliance_missing.join(", ")}.`
                      : "Mandatory compliance clear."}
                  </p>
                  {r.reminders
                    .filter(
                      (d) =>
                        d.document_type !== "POLICE_VERIFICATION" ||
                        new Date(d.expiry_date) - new Date() <= 45 * 86400000,
                    )
                    .map((d) => (
                      <p key={d.id} className="mt-1 text-amber-700">
                        {d.document_type.replaceAll("_", " ")} · expires{" "}
                        {d.expiry_date}
                      </p>
                    ))}
                </div>
              ))}
              {!alerts.length && (
                <p className="text-sm text-slate-500">No compliance alerts.</p>
              )}
            </div>
          </section>
        )}
        {tab === "reports" && (
          <section className="rounded-xl border bg-white p-5">
            <h2 className="text-lg font-semibold">Employee reports</h2>
            <div className="mt-4 flex flex-wrap gap-3">
              <select
                aria-label="Report type"
                className={inputClass + " max-w-xs"}
                value={report.kind}
                onChange={(e) => {
                  setReport((p) => ({ ...p, kind: e.target.value }));
                  setReportLoaded(false);
                }}
              >
                {["master", "attendance", "compliance"].map((x) => (
                  <option key={x} value={x}>
                    {x.replace(/^./, (v) => v.toUpperCase())} report
                  </option>
                ))}
              </select>
              {report.kind === "attendance" && (
                <>
                  <label className="text-xs">
                    From
                    <input
                      type="date"
                      className={inputClass}
                      value={report.start}
                      onChange={(e) =>
                        setReport((p) => ({ ...p, start: e.target.value }))
                      }
                    />
                  </label>
                  <label className="text-xs">
                    To
                    <input
                      type="date"
                      className={inputClass}
                      value={report.end}
                      onChange={(e) =>
                        setReport((p) => ({ ...p, end: e.target.value }))
                      }
                    />
                  </label>
                </>
              )}
              {report.kind === "compliance" && (
                <select
                  aria-label="Compliance horizon"
                  className={inputClass + " max-w-40"}
                  value={report.days}
                  onChange={(e) =>
                    setReport((p) => ({ ...p, days: Number(e.target.value) }))
                  }
                >
                  <option value={30}>Next 30 days</option>
                  <option value={60}>Next 60 days</option>
                </select>
              )}
              <button
                className={buttonClass}
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    const { data } = await api.get("/erp/employees/reports", {
                      params: params(),
                    });
                    setReportRows(data);
                    setReportLoaded(true);
                  })
                }
              >
                View report
              </button>
              {can("employees.export") &&
                ["xlsx", "pdf", "csv"].map((x) => (
                  <button
                    key={x}
                    className={buttonClass}
                    disabled={busy}
                    onClick={() => download(x)}
                  >
                    Export {x.toUpperCase()}
                  </button>
                ))}
            </div>
            {reportLoaded && (
              <div className="mt-5">
                <p className="mb-3 text-sm">
                  {reportRows.length} recorded rows
                  {report.kind === "attendance"
                    ? ` · Present ${reportRows.filter((r) => ["PRESENT", "LATE", "HALF_DAY"].includes(r.status)).length} · Absent ${reportRows.filter((r) => r.status === "ABSENT").length} · Night ${reportRows.filter((r) => r.night_shift).length} · OT ${reportRows.reduce((s, r) => s + Number(r.overtime_hours || 0), 0).toFixed(2)} h · Late ${reportRows.filter((r) => Number(r.late_minutes) > 0).length}`
                    : ""}
                </p>
                <div className="overflow-auto">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr>
                        {Object.keys(reportRows[0] || {})
                          .filter(
                            (k) =>
                              ![
                                "id",
                                "compliance_missing",
                                "reminders",
                              ].includes(k),
                          )
                          .map((k) => (
                            <th key={k} className="border-b p-2">
                              {label(k)}
                            </th>
                          ))}
                      </tr>
                    </thead>
                    <tbody>
                      {reportRows.map((r, i) => (
                        <tr key={i}>
                          {Object.entries(r)
                            .filter(
                              ([k]) =>
                                ![
                                  "id",
                                  "compliance_missing",
                                  "reminders",
                                ].includes(k),
                            )
                            .map(([k, v]) => (
                              <td key={k} className="border-b p-2">
                                {String(v ?? "—")}
                              </td>
                            ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!reportRows.length && (
                  <p className="text-sm text-slate-500">
                    No records in this report. Unrecorded shifts are not counted
                    as absence.
                  </p>
                )}
              </div>
            )}
          </section>
        )}
      </div>
      {record && (
        <div
          className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/50 p-3 sm:p-6"
          role="dialog"
          aria-modal="true"
          aria-label="Employee file"
        >
          <div className="mx-auto max-w-5xl rounded-2xl bg-white p-5">
            <div className="flex justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold">
                  {record.employee_code} · {record.name}
                </h2>
                <p className="mt-1 text-sm text-slate-500">
                  {record.intimation_id} · {record.joining_status} · Version{" "}
                  {record.version}
                </p>
              </div>
              <button
                disabled={busy}
                onClick={() => {
                  if (
                    !dirty ||
                    window.confirm("Close without saving your changes?")
                  )
                    setRecord(null);
                }}
                className="text-sm font-semibold"
              >
                Close
              </button>
            </div>
            <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs">
              {record.joining_status === "APPROVED"
                ? "Approved employee file. Identity and joining information are retained; renew compliance documents below."
                : "Complete details and upload required documents. Pending files are locked until returned. Reviewers must verify all required documents before activation."}
            </p>
            {error && (
              <p
                role="alert"
                className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700"
              >
                {error}
              </p>
            )}
            {message && (
              <p
                role="status"
                className="mt-3 rounded-lg bg-green-50 p-3 text-sm text-green-800"
              >
                {message}
              </p>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                save();
              }}
              className="mt-5 space-y-5"
            >
              <fieldset disabled={busy || !editable}>
                {groups
                  .filter(
                    ([title]) =>
                      title !== "Gunman information" ||
                      form.category === "GUNMAN",
                  )
                  .map(([title, fields]) => (
                    <section key={title} className="mb-5">
                      <h3 className="border-b pb-2 font-semibold">{title}</h3>
                      <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {fields.map((name) => (
                          <Field
                            key={name}
                            name={name}
                            value={form[name]}
                            options={options}
                            profile={form}
                            onChange={(value) => update(name, value)}
                          />
                        ))}
                      </div>
                      {title === "Bank details" && editable && (
                        <button
                          type="button"
                          disabled={busy || !form.bank_ifsc}
                          className={buttonClass + " mt-3"}
                          onClick={() =>
                            run(async () => {
                              const { data } = await api.get(
                                "/erp/employees/ifsc-check",
                                { params: { code: form.bank_ifsc } },
                              );
                              if (!data.approved) {
                                setMessage(
                                  "IFSC is not in the approved bank database. You can save the draft; submission remains blocked.",
                                );
                                return;
                              }
                              setForm((p) => ({
                                ...p,
                                bank_ifsc: data.bank.ifsc_code,
                                bank_name: data.bank.bank_name,
                                bank_branch: data.bank.branch_name,
                              }));
                              setDirty(true);
                              setMessage(
                                "Approved IFSC matched. Bank and branch filled. Save this draft.",
                              );
                            })
                          }
                        >
                          Verify IFSC & fill bank
                        </button>
                      )}
                    </section>
                  ))}
              </fieldset>
              {editable && (
                <div className="flex flex-wrap gap-3">
                  <button className={buttonClass} disabled={busy || !dirty}>
                    Save draft
                  </button>
                  <button
                    type="button"
                    className={buttonClass}
                    disabled={busy || dirty}
                    onClick={submit}
                  >
                    {user.role === "OWNER"
                      ? "Submit & activate"
                      : "Submit for approval"}
                  </button>
                </div>
              )}
            </form>
            {editable && (
              <p className="mt-3 text-xs text-slate-500">
                Still required:{" "}
                {record.readiness.missing_fields.join(", ") ||
                  "details complete"}{" "}
                · Documents:{" "}
                {record.readiness.missing_documents.join(", ") || "uploaded"}.
                Save changes before submission.
              </p>
            )}
            <section className="mt-6 border-t pt-5">
              <h3 className="font-semibold">Private compliance documents</h3>
              <p className="mt-1 text-xs text-slate-500">
                PDF, JPG, PNG or WEBP · maximum 3 MB · files stay private.
                Medical fitness expires annually. Keep older documents when
                uploading renewals.
              </p>
              {can("employees.create") &&
                !["PENDING_APPROVAL", "TERMINATED"].includes(
                  record.status.toUpperCase(),
                ) && (
                  <form
                    className="mt-4"
                    onSubmit={(e) => {
                      e.preventDefault();
                      run(async () => {
                        if (!file) return;
                        const body = new FormData();
                        Object.entries(docForm).forEach(([k, v]) => {
                          if (v) body.append(k, v);
                        });
                        body.append("file", file);
                        await api.post(
                          `/erp/employees/${record.id}/documents`,
                          body,
                          {
                            headers: { "Content-Type": "multipart/form-data" },
                          },
                        );
                        await refreshDocs();
                        setMessage(
                          "Document uploaded. Verify it after checking the original file.",
                        );
                      });
                    }}
                  >
                    <fieldset
                      disabled={busy || dirty}
                      className="grid gap-3 sm:grid-cols-3"
                    >
                      <label className="text-xs">
                        Document type
                        <select
                          className={inputClass}
                          value={docForm.document_type}
                          onChange={(e) =>
                            setDocForm((p) => ({
                              ...p,
                              document_type: e.target.value,
                            }))
                          }
                        >
                          {types.map((x) => (
                            <option key={x}>{x}</option>
                          ))}
                        </select>
                      </label>
                      {[
                        "document_number",
                        "issuing_authority",
                        "issue_date",
                        "expiry_date",
                      ].map((k) => (
                        <label key={k} className="text-xs">
                          {label(k)}
                          <input
                            className={inputClass}
                            type={k.endsWith("_date") ? "date" : "text"}
                            value={docForm[k]}
                            onChange={(e) =>
                              setDocForm((p) => ({ ...p, [k]: e.target.value }))
                            }
                          />
                        </label>
                      ))}
                      <label className="text-xs">
                        Upload document
                        <input
                          key={fileKey}
                          required
                          type="file"
                          accept=".pdf,.jpg,.jpeg,.png,.webp"
                          className={inputClass}
                          onChange={(e) => {
                            const f = e.target.files?.[0];
                            if (f && f.size > 3 * 1024 * 1024) {
                              setError("Choose a document smaller than 3 MB.");
                              setFile(null);
                            } else setFile(f);
                          }}
                        />
                      </label>
                    </fieldset>
                    <button
                      className={buttonClass + " mt-3"}
                      disabled={busy || dirty || !file}
                    >
                      Upload document
                    </button>
                  </form>
                )}
              <div className="mt-4 space-y-3">
                {documents.map((d) => (
                  <div key={d.id} className="rounded-lg border p-3 text-sm">
                    <div className="flex flex-wrap justify-between gap-2">
                      <div>
                        <strong>{d.document_type.replaceAll("_", " ")}</strong>
                        <p className="mt-1 text-xs text-slate-500">
                          {d.original_filename} · {d.verification_status} ·{" "}
                          {d.expiry_date
                            ? `Expires ${d.expiry_date}`
                            : "No expiry"}
                        </p>
                        {d.verification_notes && (
                          <p className="mt-1 text-xs">{d.verification_notes}</p>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-3">
                        <button
                          disabled={busy || dirty}
                          className="text-teal-700"
                          onClick={() =>
                            run(async () => {
                              const { data } = await api.post(
                                `/erp/employees/${record.id}/documents/${d.id}/sign`,
                              );
                              window.open(
                                data.url,
                                "_blank",
                                "noopener,noreferrer",
                              );
                            })
                          }
                        >
                          Open
                        </button>
                        {can("employees.approve") &&
                          (!submittedApproval ||
                            submittedApproval.assigned_to === user.id ||
                            user.role === "OWNER") && (
                            <>
                              <button
                                disabled={busy || dirty}
                                className="text-teal-700"
                                onClick={() =>
                                  run(async () => {
                                    await api.patch(
                                      `/erp/employees/${record.id}/documents/${d.id}/verify`,
                                      { status: "VERIFIED" },
                                    );
                                    await refreshDocs();
                                    setMessage("Document verified.");
                                  })
                                }
                              >
                                Verify
                              </button>
                              <button
                                disabled={busy || dirty}
                                className="text-red-700"
                                onClick={() => {
                                  const notes = window.prompt(
                                    "Reason for rejecting this document",
                                  );
                                  if (notes)
                                    run(async () => {
                                      await api.patch(
                                        `/erp/employees/${record.id}/documents/${d.id}/verify`,
                                        { status: "REJECTED", notes },
                                      );
                                      await refreshDocs();
                                    });
                                }}
                              >
                                Reject
                              </button>
                            </>
                          )}
                      </div>
                    </div>
                  </div>
                ))}
                {!documents.length && (
                  <p className="text-sm text-slate-500">
                    No documents uploaded.
                  </p>
                )}
              </div>
            </section>
            {submittedApproval && can("employees.approve") && (
              <section className="mt-6 rounded-xl bg-slate-50 p-4">
                <h3 className="font-semibold">Joining approval</h3>
                <p className="mt-2 text-xs">
                  Review all details and documents. All required documents must
                  be verified to approve.
                </p>
                <textarea
                  aria-label="Approval or return remarks"
                  className={inputClass + " mt-3"}
                  placeholder="Approval notes / required return remarks"
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                />
                <div className="mt-3 flex gap-3">
                  <button
                    disabled={busy}
                    className={buttonClass}
                    onClick={() => decision("APPROVE")}
                  >
                    Approve
                  </button>
                  <button
                    disabled={busy || !remarks.trim()}
                    className={buttonClass}
                    onClick={() => decision("REJECT")}
                  >
                    Return for correction
                  </button>
                </div>
              </section>
            )}
            {record.joining_status === "APPROVED" &&
              can("employees.edit") &&
              ["OWNER", "SUPER_ADMIN", "ADMIN"].includes(user.role) && (
                <section className="mt-6 border-t pt-4">
                  <h3 className="font-semibold">Employment status</h3>
                  <div className="mt-3 flex flex-wrap gap-3">
                    <select
                      aria-label="New employment status"
                      className={inputClass + " max-w-xs"}
                      value={stateForm.status}
                      onChange={(e) =>
                        setStateForm((p) => ({ ...p, status: e.target.value }))
                      }
                    >
                      {["ACTIVE", "BENCH", "INACTIVE", "TERMINATED"].map(
                        (x) => (
                          <option key={x}>{x}</option>
                        ),
                      )}
                    </select>
                    <input
                      aria-label="Status reason"
                      className={inputClass + " max-w-sm"}
                      placeholder="Required reason"
                      value={stateForm.reason}
                      onChange={(e) =>
                        setStateForm((p) => ({ ...p, reason: e.target.value }))
                      }
                    />
                    <button
                      disabled={busy || !stateForm.reason.trim()}
                      className={buttonClass}
                      onClick={() =>
                        run(async () => {
                          await api.patch(
                            `/erp/employees/${record.id}/status`,
                            { ...stateForm, version: record.version },
                          );
                          await openRecord(record.id);
                          await load();
                          setMessage("Employment status updated and recorded.");
                        })
                      }
                    >
                      Update status
                    </button>
                  </div>
                </section>
              )}
            <section className="mt-6 border-t pt-4">
              <h3 className="font-semibold">Employee file history</h3>
              <div className="mt-3 space-y-2 text-xs text-slate-500">
                {history.map((h) => (
                  <p key={h.id}>
                    {new Date(h.created_at).toLocaleString()} ·{" "}
                    {h.action.replaceAll("_", " ")} ·{" "}
                    {h.changed_by_name || "System"}
                    {h.details?.remarks ? ` · ${h.details.remarks}` : ""}
                  </p>
                ))}
              </div>
            </section>
          </div>
        </div>
      )}
    </MainLayout>
  );
}

function EmployeeTable({ rows, loading, onOpen }) {
  return (
    <div className="overflow-auto rounded-xl border bg-white">
      <table className="w-full min-w-[850px] text-left text-sm">
        <thead className="bg-slate-50 text-xs text-slate-500">
          <tr>
            {[
              "Employee",
              "Employee ID",
              "Client / branch",
              "Designation",
              "Status",
              "File",
            ].map((x) => (
              <th key={x} className="p-4">
                {x}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} className="border-t">
              <td className="p-4 font-medium">
                {r.name}
                <p className="mt-1 text-xs text-slate-500">
                  {r.phone} · {r.aadhaar_masked || "—"}
                </p>
              </td>
              <td className="p-4 font-mono text-xs">
                {r.employee_code}
                <p className="mt-1 text-slate-500">{r.intimation_id}</p>
              </td>
              <td className="p-4">
                {r.client_name || "—"}
                <p className="text-xs text-slate-500">
                  {r.branch} · {r.site_name || "Site not assigned"}
                </p>
              </td>
              <td className="p-4">
                {r.designation || "Joining details pending"}
              </td>
              <td className="p-4 text-xs">
                {r.status}
                <p className="mt-1 text-slate-500">{r.joining_status}</p>
              </td>
              <td className="p-4">
                <button
                  onClick={() => onOpen(r.id)}
                  className="font-semibold text-teal-700"
                >
                  Open file
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {loading ? (
        <p className="p-8 text-center text-sm text-slate-500">
          Loading employees…
        </p>
      ) : (
        !rows.length && (
          <p className="p-8 text-center text-sm text-slate-500">
            No employee records here yet.
          </p>
        )
      )}
    </div>
  );
}
