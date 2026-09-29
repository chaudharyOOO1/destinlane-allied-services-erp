import React, { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  BadgeCheck,
  Building2,
  CalendarDays,
  Clock,
  Download,
  FileText,
  IdCard,
  Menu,
  User,
  X,
} from "lucide-react";
import { supabase } from "@/api/supabaseClient";

function InfoRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center gap-3 py-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-slate-400">{label}</p>
        <p className="truncate text-sm font-medium text-slate-900">{value || "—"}</p>
      </div>
    </div>
  );
}

function formatDate(d) {
  if (!d) return "—";
  return new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

const documentLabels = {
  form_11: "Form 11",
  form_11a: "Form 11A",
  police_verification: "Police Verification",
  esic_form: "ESIC Form",
};

export default function EmployeeProfile({ employee }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [section, setSection] = useState("personal");
  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);

  const shift =
    employee.shift_start && employee.shift_end
      ? `${employee.shift_start} – ${employee.shift_end}`
      : null;

  const employeeFieldDocuments = useMemo(() => {
    return Object.entries(documentLabels)
      .map(([key, label]) => {
        const url =
          employee?.[`${key}_url`] ||
          employee?.[`${key}_document_url`] ||
          employee?.[`${key}_document`];

        return url ? { id: key, name: label, url } : null;
      })
      .filter(Boolean);
  }, [employee]);

  useEffect(() => {
    let cancelled = false;

    const loadDocuments = async () => {
      setDocumentsLoading(true);

      try {
        // Preferred backend model: employee_documents table.
        // If it is not present yet, we silently fall back to document URL
        // fields on the employee record.
        const { data, error } = await supabase
          .from("employee_documents")
          .select("*")
          .eq("employee_id", employee.id)
          .order("created_at", { ascending: false });

        if (!error && !cancelled) {
          const mapped = (data || [])
            .map((doc) => ({
              id: doc.id,
              name:
                doc.name ||
                documentLabels[doc.document_type] ||
                doc.document_type ||
                "Document",
              url: doc.file_url || doc.url || doc.public_url,
            }))
            .filter((doc) => doc.url);

          setDocuments(mapped);
        } else if (!cancelled) {
          setDocuments(employeeFieldDocuments);
        }
      } catch {
        if (!cancelled) setDocuments(employeeFieldDocuments);
      } finally {
        if (!cancelled) setDocumentsLoading(false);
      }
    };

    if (section === "documents") {
      loadDocuments();
    }

    return () => {
      cancelled = true;
    };
  }, [employee, employeeFieldDocuments, section]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm"
    >
      <div className="relative flex items-center gap-4 bg-gradient-to-r from-slate-900 to-slate-800 px-6 py-5">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-white/10 text-lg font-semibold text-white ring-1 ring-white/20">
          {employee.name?.charAt(0)?.toUpperCase() || "?"}
        </div>

        <div className="min-w-0 flex-1">
          <h2 className="truncate text-lg font-semibold text-white">{employee.name}</h2>
          <p className="truncate text-sm text-slate-300">{employee.designation || "Employee"}</p>
        </div>

        {employee.status === "active" && (
          <span className="mr-1 flex items-center gap-1 rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-medium text-emerald-300 ring-1 ring-emerald-500/20">
            <BadgeCheck className="h-3.5 w-3.5" />
            Active
          </span>
        )}

        <button
          type="button"
          aria-label="Employee information menu"
          onClick={() => setMenuOpen((open) => !open)}
          className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-white hover:bg-white/20"
        >
          <Menu className="h-5 w-5" />
        </button>

        {menuOpen && (
          <div className="absolute right-5 top-[72px] z-20 w-52 overflow-hidden rounded-xl border border-slate-200 bg-white p-1.5 text-slate-700 shadow-xl">
            <button
              type="button"
              onClick={() => {
                setSection("personal");
                setMenuOpen(false);
              }}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium hover:bg-slate-50"
            >
              <User className="h-4 w-4 text-slate-500" />
              Personal Details
            </button>
            <button
              type="button"
              onClick={() => {
                setSection("documents");
                setMenuOpen(false);
              }}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium hover:bg-slate-50"
            >
              <FileText className="h-4 w-4 text-slate-500" />
              Documents
            </button>
          </div>
        )}
      </div>

      {section === "personal" ? (
        <div className="divide-y divide-slate-50 px-6">
          <InfoRow icon={IdCard} label="Employee Code" value={employee.employee_code} />
          <InfoRow icon={User} label="Designation" value={employee.designation} />
          <InfoRow icon={CalendarDays} label="Date of Joining" value={formatDate(employee.doj)} />
          <InfoRow icon={Building2} label="Assigned Site" value={employee.assigned_site} />
          <InfoRow icon={Clock} label="Shift Timing" value={shift} />
          <InfoRow icon={User} label="Phone" value={employee.phone} />
          <InfoRow icon={IdCard} label="Date of Birth" value={formatDate(employee.dob)} />
          <InfoRow icon={User} label="Father's Name" value={employee.father_name} />
          <InfoRow icon={Building2} label="Address" value={employee.address} />
        </div>
      ) : (
        <div className="p-5">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Documents</h3>
              <p className="mt-1 text-xs text-slate-400">Download documents available for your employee record.</p>
            </div>
            <button
              type="button"
              onClick={() => setSection("personal")}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              aria-label="Close documents"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          {documentsLoading ? (
            <div className="rounded-xl bg-slate-50 px-4 py-6 text-center text-sm text-slate-400">
              Loading documents…
            </div>
          ) : documents.length > 0 ? (
            <div className="space-y-2">
              {documents.map((doc) => (
                <a
                  key={doc.id || doc.name}
                  href={doc.url}
                  target="_blank"
                  rel="noreferrer"
                  download
                  className="flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50 px-4 py-3 transition hover:bg-slate-100"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-slate-500">
                      <FileText className="h-4 w-4" />
                    </div>
                    <span className="truncate text-sm font-medium text-slate-800">{doc.name}</span>
                  </div>
                  <Download className="h-4 w-4 shrink-0 text-slate-500" />
                </a>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 px-4 py-6 text-center text-sm text-slate-400">
              No documents are available yet.
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}
