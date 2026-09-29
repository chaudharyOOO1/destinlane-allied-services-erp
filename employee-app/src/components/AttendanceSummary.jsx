import React from "react";
import { motion } from "framer-motion";
import { CalendarCheck, Clock, CalendarOff, UserX } from "lucide-react";

function StatCard({ icon: Icon, label, value, accent, delay }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay, ease: "easeOut" }}
      className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
    >
      <div className={`mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl ${accent}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="text-2xl font-semibold tracking-tight text-slate-900">{value}</div>
      <div className="mt-0.5 text-sm text-slate-500">{label}</div>
    </motion.div>
  );
}

export default function AttendanceSummary({ stats }) {
  return (
    <div>
      <h3 className="mb-3 px-1 text-sm font-semibold text-slate-700">
        This Month
      </h3>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon={CalendarCheck}
          label="Present Days"
          value={stats.present}
          accent="bg-emerald-50 text-emerald-600"
          delay={0.05}
        />
        <StatCard
          icon={Clock}
          label="Late Logins"
          value={stats.late}
          accent="bg-amber-50 text-amber-600"
          delay={0.1}
        />
        <StatCard
          icon={CalendarOff}
          label="Leaves"
          value={stats.leave}
          accent="bg-indigo-50 text-indigo-600"
          delay={0.15}
        />
        <StatCard
          icon={UserX}
          label="Absent"
          value={stats.absent}
          accent="bg-rose-50 text-rose-600"
          delay={0.2}
        />
      </div>
    </div>
  );
}