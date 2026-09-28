import React from "react";
import { motion, AnimatePresence } from "framer-motion";
import { LogIn, LogOut, Clock3 } from "lucide-react";
import { Image } from "@/components/ui/image";

function statusBadge(status) {
  const map = {
    present: "bg-emerald-50 text-emerald-700 ring-emerald-600/10",
    late: "bg-amber-50 text-amber-700 ring-amber-600/10",
    half_day: "bg-indigo-50 text-indigo-700 ring-indigo-600/10",
    absent: "bg-rose-50 text-rose-700 ring-rose-600/10",
  };
  const label = {
    present: "Present",
    late: "Late",
    half_day: "Half Day",
    absent: "Absent",
  };
  return (
    <span className={`rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${map[status] || ""}`}>
      {label[status] || status}
    </span>
  );
}

function fmtTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function fmtDate(dateStr) {
  const d = new Date(dateStr + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const diff = Math.round((today - d) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

export default function AttendanceHistory({ records }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
        <h3 className="font-semibold text-slate-900">Recent Attendance</h3>
        <span className="text-sm text-slate-400">{records.length} records</span>
      </div>

      {records.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <Clock3 className="h-8 w-8 text-slate-300" />
          <p className="mt-3 text-sm text-slate-500">No attendance records yet.</p>
          <p className="text-xs text-slate-400">Your check-ins will appear here.</p>
        </div>
      ) : (
        <ul className="divide-y divide-slate-50">
          <AnimatePresence initial={false}>
            {records.map((r, i) => (
              <motion.li
                key={r.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: i * 0.03 }}
                className="flex items-center gap-4 px-5 py-4"
              >
                {r.photo_url && (
                  <Image
                    src={r.photo_url}
                    alt="Login selfie"
                    className="h-10 w-10 shrink-0 overflow-hidden rounded-full"
                  />
                )}

                <div className="flex w-20 shrink-0 flex-col">
                  <span className="text-sm font-semibold text-slate-900">{fmtDate(r.date)}</span>
                </div>

                <div className="flex flex-1 items-center gap-4 text-sm text-slate-600">
                  <span className="flex items-center gap-1.5">
                    <LogIn className="h-3.5 w-3.5 text-emerald-500" />
                    {fmtTime(r.check_in_time)}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <LogOut className="h-3.5 w-3.5 text-indigo-500" />
                    {fmtTime(r.check_out_time)}
                  </span>
                </div>

                <div className="hidden sm:block text-sm font-medium text-slate-700 tabular-nums">
                  {r.work_hours != null ? `${Number(r.work_hours).toFixed(2)}h` : "—"}
                </div>

                {statusBadge(r.status)}
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}