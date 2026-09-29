import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Wallet, Download, CheckCircle2, Clock3, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { generateSalarySlip } from "@/lib/salarySlip";

function monthLabel(monthStr) {
  if (!monthStr) return "—";
  const [y, m] = monthStr.split("-");
  const d = new Date(Number(y), Number(m) - 1, 1);
  return d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

export default function SalaryCard({ employee, salaryRecords }) {
  const records = salaryRecords || [];
  const [selectedMonth, setSelectedMonth] = useState("");

  useEffect(() => {
    if (!records.length) {
      setSelectedMonth("");
      return;
    }

    // Keep the user's selection when it still exists, but automatically
    // select a newly-added latest month after the backend refreshes.
    setSelectedMonth((current) => {
      if (!current) return records[0].month;
      if (!records.some((record) => record.month === current)) {
        return records[0].month;
      }
      if (records[0].month !== current) {
        return records[0].month;
      }
      return current;
    });
  }, [records]);

  const selected = records.find((s) => s.month === selectedMonth);
  const credited = selected?.status === "credited";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: 0.1, ease: "easeOut" }}
      className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm"
    >
      <div className="mb-4 flex items-center gap-2">
        <Wallet className="h-5 w-5 text-slate-400" />
        <h3 className="text-sm font-semibold text-slate-700">Salary</h3>
      </div>

      {records.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-6 text-center">
          <Clock3 className="h-8 w-8 text-slate-300" />
          <p className="mt-3 text-sm font-medium text-slate-500">Salary not generated yet</p>
          <p className="text-xs text-slate-400">Check back later this month</p>
        </div>
      ) : (
        <div>
          <div className="mb-3">
            <label className="mb-1.5 block text-xs font-medium text-slate-500">Select Month</label>
            <div className="relative">
              <select
                value={selectedMonth}
                onChange={(e) => setSelectedMonth(e.target.value)}
                className="w-full appearance-none rounded-lg border border-slate-200 bg-white px-3 py-2.5 pr-9 text-sm font-medium text-slate-900 outline-none focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
              >
                {records.map((r) => (
                  <option key={r.id} value={r.month}>
                    {monthLabel(r.month)} {r.status === "credited" ? "✓" : "○"}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            </div>
          </div>

          <div className="mb-1 text-sm text-slate-500">{monthLabel(selected?.month)}</div>
          <div className="text-3xl font-semibold tracking-tight text-slate-900">
            Rs. {Number(selected?.amount || 0).toLocaleString("en-IN")}
          </div>

          <div className="mt-4 flex items-center gap-2">
            {credited ? (
              <>
                <span className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700 ring-1 ring-emerald-600/10">
                  <CheckCircle2 className="h-4 w-4" />
                  Credited
                </span>
                {selected?.credited_date && (
                  <span className="text-xs text-slate-400">
                    on {new Date(selected.credited_date).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}
                  </span>
                )}
              </>
            ) : (
              <span className="flex items-center gap-1.5 rounded-full bg-amber-50 px-3 py-1.5 text-sm font-medium text-amber-700 ring-1 ring-amber-600/10">
                <Clock3 className="h-4 w-4" />
                Pending
              </span>
            )}
          </div>

          <Button
            variant="outline"
            className="mt-5 w-full"
            disabled={!selected}
            onClick={() => selected && generateSalarySlip(employee, selected)}
          >
            <Download className="mr-2 h-4 w-4" />
            Download Salary Slip
          </Button>
        </div>
      )}
    </motion.div>
  );
}