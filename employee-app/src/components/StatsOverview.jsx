import React from "react";
import { motion } from "framer-motion";
import { CalendarCheck, Clock, TrendingUp, CalendarDays } from "lucide-react";

function StatCard({ icon: Icon, label, value, sub, accent, delay }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: "easeOut" }}
      className="rounded-2xl border border-slate-100 bg-white p-5 shadow-sm"
    >
      <div className={`mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl ${accent}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="text-2xl font-semibold tracking-tight text-slate-900">{value}</div>
      <div className="mt-0.5 text-sm text-slate-500">{label}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </motion.div>
  );
}

export default function StatsOverview({ stats }) {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      <StatCard
        icon={CalendarCheck}
        label="Days present (this month)"
        value={stats.presentDays}
        accent="bg-emerald-50 text-emerald-600"
        delay={0.05}
      />
      <StatCard
        icon={Clock}
        label="Total hours (this month)"
        value={`${stats.totalHours.toFixed(1)}h`}
        accent="bg-indigo-50 text-indigo-600"
        delay={0.1}
      />
      <StatCard
        icon={TrendingUp}
        label="Avg hours / day"
        value={`${stats.avgHours.toFixed(1)}h`}
        accent="bg-amber-50 text-amber-600"
        delay={0.15}
      />
      <StatCard
        icon={CalendarDays}
        label="Attendance rate"
        value={`${stats.rate}%`}
        accent="bg-rose-50 text-rose-600"
        delay={0.2}
      />
    </div>
  );
}