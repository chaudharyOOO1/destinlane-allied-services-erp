import React, { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { LogIn, LogOut, Clock, CheckCircle2, Calendar, MapPin, Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function CheckInCard({ todayRecord, onLogin, onLogout, loading, geoStatus, geoDistance, hasGeofence }) {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const isLoggedIn = !!todayRecord?.check_in_time;
  const isLoggedOut = !!todayRecord?.check_out_time;

  const timeStr = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });

  const dateStr = now.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  const loginTime = todayRecord?.check_in_time
    ? new Date(todayRecord.check_in_time).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      })
    : null;

  const logoutTime = todayRecord?.check_out_time
    ? new Date(todayRecord.check_out_time).toLocaleTimeString("en-US", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      })
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: "easeOut" }}
      className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-8 sm:p-10 text-white shadow-xl"
    >
      <div className="absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/5 blur-2xl" />
      <div className="absolute -bottom-20 -left-10 h-56 w-56 rounded-full bg-indigo-500/10 blur-3xl" />

      <div className="relative">
        <div className="flex items-center gap-2 text-slate-300 text-sm font-medium">
          <Calendar className="h-4 w-4" />
          {dateStr}
        </div>

        <div className="mt-6 flex items-end gap-3">
          <span className="font-display text-5xl sm:text-6xl font-semibold tracking-tight tabular-nums">
            {timeStr.split(" ")[0]}
          </span>
          <span className="mb-2 text-lg font-medium text-slate-400">
            {timeStr.split(" ")[1]}
          </span>
        </div>

        <div className="mt-8 flex flex-col gap-4">
          {isLoggedIn && (
            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-2 rounded-full bg-emerald-500/15 px-4 py-2 text-sm text-emerald-300 ring-1 ring-emerald-500/20">
                <LogIn className="h-4 w-4" />
                <span className="font-medium">In: {loginTime}</span>
              </div>
              {isLoggedOut ? (
                <div className="flex items-center gap-2 rounded-full bg-indigo-500/15 px-4 py-2 text-sm text-indigo-300 ring-1 ring-indigo-500/20">
                  <LogOut className="h-4 w-4" />
                  <span className="font-medium">Out: {logoutTime}</span>
                </div>
              ) : null}
            </div>
          )}

          {!isLoggedIn && hasGeofence && geoStatus !== "idle" && (
            <div
              className={`flex items-center gap-2 rounded-2xl px-4 py-3 text-sm ring-1 ${
                geoStatus === "checking"
                  ? "bg-white/5 text-slate-300 ring-white/10"
                  : geoStatus === "inside"
                  ? "bg-emerald-500/10 text-emerald-300 ring-emerald-500/20"
                  : "bg-amber-500/10 text-amber-300 ring-amber-500/20"
              }`}
            >
              {geoStatus === "checking" && <Loader2 className="h-4 w-4 animate-spin" />}
              {geoStatus === "inside" && <MapPin className="h-4 w-4" />}
              {(geoStatus === "outside" || geoStatus === "denied") && <AlertCircle className="h-4 w-4" />}
              <span>
                {geoStatus === "checking" && "Verifying your location…"}
                {geoStatus === "inside" && "Within site geofence"}
                {geoStatus === "outside" && `${geoDistance}m from site — you can still punch in`}
                {geoStatus === "denied" && "Location unavailable — punch will be saved without GPS"}
              </span>
            </div>
          )}

          <div className="flex flex-col gap-3">
            {isLoggedOut && (
              <div className="flex items-center gap-2 text-emerald-300">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-medium">
                  Logged out at {logoutTime}. You can log in again.
                </span>
              </div>
            )}

            <Button
              size="lg"
              disabled={loading || (!isLoggedIn && geoStatus === "checking")}
              onClick={isLoggedIn && !isLoggedOut ? onLogout : onLogin}
              className="w-full sm:w-auto rounded-full bg-white px-8 py-6 text-base font-semibold text-slate-900 hover:bg-slate-100 disabled:opacity-60"
            >
              {loading ? (
                <>
                  <Clock className="mr-2 h-5 w-5 animate-spin" />
                  Please wait...
                </>
              ) : isLoggedIn && !isLoggedOut ? (
                <>
                  <LogOut className="mr-2 h-5 w-5" />
                  Logout
                </>
              ) : (
                <>
                  <LogIn className="mr-2 h-5 w-5" />
                  Login Again
                </>
              )}
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}