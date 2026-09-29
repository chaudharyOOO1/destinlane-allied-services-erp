import React, { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight, CalendarDays } from "lucide-react";
import { Image } from "@/components/ui/image";

const STATUS_STYLES = {
  present: { bg: "bg-emerald-500", text: "text-white", label: "Present", dot: "bg-emerald-500" },
  late: { bg: "bg-amber-500", text: "text-white", label: "Late", dot: "bg-amber-500" },
  half_day: { bg: "bg-sky-500", text: "text-white", label: "Half Day", dot: "bg-sky-500" },
  leave: { bg: "bg-indigo-500", text: "text-white", label: "Leave", dot: "bg-indigo-500" },
  absent: { bg: "bg-rose-500", text: "text-white", label: "Absent", dot: "bg-rose-500" },
};

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function AttendanceCalendar({ records }) {
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());
  const [selectedDate, setSelectedDate] = useState(null);

  const recordsByDate = useMemo(() => {
    const map = {};
    (records || []).forEach((r) => {
      if (r.date) map[r.date] = r;
    });
    return map;
  }, [records]);

  const calendarDays = useMemo(() => {
    const firstDay = new Date(viewYear, viewMonth, 1);
    const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
    const startOffset = firstDay.getDay();
    const cells = [];
    for (let i = 0; i < startOffset; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
      cells.push({ day: d, dateStr, record: recordsByDate[dateStr] || null });
    }
    return cells;
  }, [viewYear, viewMonth, recordsByDate]);

  const monthStats = useMemo(() => {
    const counts = { present: 0, late: 0, half_day: 0, leave: 0, absent: 0 };
    calendarDays.forEach((c) => {
      if (c?.record?.status) counts[c.record.status] = (counts[c.record.status] || 0) + 1;
    });
    return counts;
  }, [calendarDays]);

  const goPrev = () => {
    if (viewMonth === 0) {
      setViewMonth(11);
      setViewYear((y) => y - 1);
    } else {
      setViewMonth((m) => m - 1);
    }
    setSelectedDate(null);
  };

  const goNext = () => {
    if (viewMonth === 11) {
      setViewMonth(0);
      setViewYear((y) => y + 1);
    } else {
      setViewMonth((m) => m + 1);
    }
    setSelectedDate(null);
  };

  const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const isCurrentMonth = viewYear === today.getFullYear() && viewMonth === today.getMonth();
  const selectedRecord = selectedDate ? recordsByDate[selectedDate] : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm"
    >
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CalendarDays className="h-5 w-5 text-slate-400" />
          <h3 className="text-sm font-semibold text-slate-700">
            {MONTH_NAMES[viewMonth]} {viewYear}
          </h3>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={goPrev}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            onClick={goNext}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Weekday headers */}
      <div className="mb-2 grid grid-cols-7 gap-1.5">
        {WEEKDAYS.map((w) => (
          <div key={w} className="py-1 text-center text-[11px] font-medium uppercase tracking-wide text-slate-400">
            {w}
          </div>
        ))}
      </div>

      {/* Calendar grid */}
      <div className="grid grid-cols-7 gap-1.5">
        {calendarDays.map((cell, idx) => {
          if (!cell) return <div key={`empty-${idx}`} className="aspect-square" />;
          const isToday = cell.dateStr === todayStr;
          const isSelected = cell.dateStr === selectedDate;
          const style = cell.record?.status ? STATUS_STYLES[cell.record.status] : null;
          const isFuture = new Date(cell.dateStr) > today && !isToday;

          return (
            <button
              key={cell.dateStr}
              onClick={() => setSelectedDate(cell.dateStr)}
              className={`
                relative flex aspect-square flex-col items-center justify-center rounded-lg text-sm font-medium transition-all
                ${isSelected ? "ring-2 ring-slate-900 ring-offset-1" : ""}
                ${style ? `${style.bg} ${style.text}` : isFuture ? "text-slate-300" : "text-slate-600 hover:bg-slate-100"}
                ${isToday && !style ? "ring-1 ring-slate-300" : ""}
              `}
            >
              <span>{cell.day}</span>
              {style && (
                <span className={`mt-0.5 text-[9px] font-medium ${style.text} opacity-80`}>
                  {cell.record.check_in_time
                    ? new Date(cell.record.check_in_time).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false })
                    : ""}
                </span>
              )}
              {isToday && <span className="absolute -bottom-0.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-slate-900" />}
            </button>
          );
        })}
      </div>

      {/* Selected day detail */}
      <AnimatePresence mode="wait">
        {selectedDate && (
          <motion.div
            key={selectedDate}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
            className="mt-4 overflow-hidden"
          >
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="flex items-center justify-between gap-3">
                {selectedRecord?.photo_url && (
                  <Image
                    src={selectedRecord.photo_url}
                    alt="Login selfie"
                    className="h-14 w-14 shrink-0 overflow-hidden rounded-xl"
                  />
                )}
                <div className="flex-1">
                  <p className="text-xs text-slate-400">
                    {new Date(selectedDate + "T00:00:00").toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
                  </p>
                  {selectedRecord ? (
                    <div className="mt-1 flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${STATUS_STYLES[selectedRecord.status]?.dot || "bg-slate-300"}`} />
                      <span className="text-sm font-semibold capitalize text-slate-800">
                        {STATUS_STYLES[selectedRecord.status]?.label || selectedRecord.status}
                      </span>
                    </div>
                  ) : (
                    <p className="mt-1 text-sm font-medium text-slate-400">No record</p>
                  )}
                </div>
                {selectedRecord && (
                  <div className="space-y-0.5 text-right text-xs text-slate-500">
                    {selectedRecord.check_in_time && (
                      <p>In: <span className="font-medium text-slate-700">{new Date(selectedRecord.check_in_time).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true })}</span></p>
                    )}
                    {selectedRecord.check_out_time && (
                      <p>Out: <span className="font-medium text-slate-700">{new Date(selectedRecord.check_out_time).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: true })}</span></p>
                    )}
                    {selectedRecord.work_hours != null && (
                      <p><span className="font-medium text-slate-700">{Number(selectedRecord.work_hours).toFixed(2)} hrs</span></p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-slate-50 pt-4">
        {Object.entries(STATUS_STYLES).map(([key, val]) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className={`h-2.5 w-2.5 rounded-full ${val.dot}`} />
            <span className="text-xs text-slate-500">
              {val.label} {monthStats[key] > 0 && <span className="font-medium text-slate-700">({monthStats[key]})</span>}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}