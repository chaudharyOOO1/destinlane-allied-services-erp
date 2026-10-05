import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Clock } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

import { mobileApi } from "@/api/backendClient";
import { getSession, setSession, clearSession } from "@/lib/phoneSession";
import { getCurrentPosition } from "@/lib/geofence";

import CheckInCard from "@/components/CheckInCard";
import EmployeeProfile from "@/components/EmployeeProfile";
import AttendanceSummary from "@/components/AttendanceSummary";
import SalaryCard from "@/components/SalaryCard";
import AttendanceHistory from "@/components/AttendanceHistory";
import AttendanceCalendar from "@/components/AttendanceCalendar";
import SelfieCapture from "@/components/SelfieCapture";

function todayStr() {
  return new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
}

function getDeviceId() {
  const existing = localStorage.getItem("emp_device_id");
  if (existing) return existing;
  const id = globalThis.crypto?.randomUUID?.() || `device-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  localStorage.setItem("emp_device_id", id);
  return id;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [employee, setEmployee] = useState(() => getSession());
  const [todayRecord, setTodayRecord] = useState(null);
  const [records, setRecords] = useState([]);
  const [salaryRecords, setSalaryRecords] = useState([]);
  const [stats, setStats] = useState({ present: 0, late: 0, leave: 0, absent: 0 });
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [geoStatus, setGeoStatus] = useState("idle");
  const [geoDistance, setGeoDistance] = useState(null);
  const [selfieOpen, setSelfieOpen] = useState(false);
  const [punchType, setPunchType] = useState(null);
  const [punchTime, setPunchTime] = useState(null);
  const [punchCoords, setPunchCoords] = useState(null);

  const hasGeofence = employee?.site_latitude != null && employee?.site_longitude != null;

  const loadData = useCallback(async () => {
    if (!getSession()) {
      navigate("/login");
      return;
    }
    try {
      const [freshEmployee, attendance, salary] = await Promise.all([
        mobileApi.me(),
        mobileApi.attendance(),
        mobileApi.salary(),
      ]);

      setEmployee(freshEmployee);
      setSession(freshEmployee);
      setRecords(attendance || []);
      setSalaryRecords(salary || []);

      const today = todayStr();
      setTodayRecord((attendance || []).find((record) => record.check_in_time && !record.check_out_time) || (attendance || []).find((record) => record.attendance_date === today) || null);

      const month = today.slice(0, 7);
      const monthAttendance = (attendance || []).filter((record) => record.attendance_date?.startsWith(month));
      setStats({
        present: monthAttendance.filter((record) => record.status === "present").length,
        late: monthAttendance.filter((record) => record.status === "late").length,
        leave: monthAttendance.filter((record) => record.status === "leave").length,
        absent: monthAttendance.filter((record) => record.status === "absent").length,
      });
    } catch (error) {
      console.error("Failed to load employee data:", error);
      if (/session|expired|inactive|invalid/i.test(error?.message || "")) {
        localStorage.removeItem("emp_access_token");
        clearSession();
        navigate("/login");
      } else {
        toast({ title: "Failed to load data", description: error?.message || "Please refresh and try again.", variant: "destructive" });
      }
    } finally {
      setInitialLoading(false);
    }
  }, [navigate, toast]);

  useEffect(() => {
    loadData();
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") loadData();
    };
    document.addEventListener("visibilitychange", refreshWhenVisible);
    window.addEventListener("focus", refreshWhenVisible);
    const refreshTimer = window.setInterval(() => {
      if (document.visibilityState === "visible") loadData();
    }, 30000);
    return () => {
      document.removeEventListener("visibilitychange", refreshWhenVisible);
      window.removeEventListener("focus", refreshWhenVisible);
      window.clearInterval(refreshTimer);
    };
  }, [loadData]);

  const calculateDistance = (lat1, lng1, lat2, lng2) => {
    const earthRadius = 6371000;
    const latitude1 = (lat1 * Math.PI) / 180;
    const latitude2 = (lat2 * Math.PI) / 180;
    const deltaLatitude = ((lat2 - lat1) * Math.PI) / 180;
    const deltaLongitude = ((lng2 - lng1) * Math.PI) / 180;
    const a = Math.sin(deltaLatitude / 2) ** 2 +
      Math.cos(latitude1) * Math.cos(latitude2) * Math.sin(deltaLongitude / 2) ** 2;
    return earthRadius * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  };

  const startPunch = async (type) => {
    setLoading(true);
    setPunchType(type);
    try {
      const now = new Date().toISOString();
      let coords = null;
      try {
        coords = await getCurrentPosition();
      } catch (error) {
        console.warn("GPS unavailable:", error);
      }

      if (hasGeofence && coords) {
        const distance = Math.round(calculateDistance(
          coords.lat,
          coords.lng,
          Number(employee.site_latitude),
          Number(employee.site_longitude)
        ));
        setGeoDistance(distance);
        setGeoStatus(distance <= Number(employee.geofence_radius || 100) ? "inside" : "outside");
      } else {
        setGeoStatus("idle");
        setGeoDistance(null);
      }

      setPunchTime(now);
      setPunchCoords(coords);
      setSelfieOpen(true);
    } catch (error) {
      toast({ title: type === "check-in" ? "Check-in failed" : "Check-out failed", description: error?.message || "Please try again.", variant: "destructive" });
      setPunchType(null);
    } finally {
      setLoading(false);
    }
  };

  const handleSelfieConfirm = async (file) => {
    setSelfieOpen(false);
    setLoading(true);
    try {
      if (!employee?.id || !punchCoords) {
        throw new Error("Employee session or GPS location is missing.");
      }

      const selfie = await mobileApi.uploadSelfie(file, punchType);
      const result = await mobileApi.punch({
        action: punchType === "check-in" ? "CHECK_IN" : "CHECK_OUT",
        latitude: punchCoords.lat,
        longitude: punchCoords.lng,
        accuracy: punchCoords.accuracy ?? null,
        device_id: getDeviceId(),
        ...(punchType === "check-in"
          ? { check_in_selfie_path: selfie.path }
          : { check_out_selfie_path: selfie.path }),
      });

      toast({
        title: result.action === "CHECK_IN" ? "Checked in" : "Checked out",
        description: result.action === "CHECK_OUT" && result.shift_hours
          ? `Worked ${Number(result.shift_hours).toFixed(2)} hrs`
          : "Attendance has been securely recorded.",
      });
      await loadData();
    } catch (error) {
      toast({
        title: punchType === "check-in" ? "Check-in failed" : "Check-out failed",
        description: error?.message || "Something went wrong. Please try again.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
      setPunchType(null);
      setPunchTime(null);
      setPunchCoords(null);
    }
  };

  const handleSignOut = () => {
    localStorage.removeItem("emp_access_token");
    clearSession();
    navigate("/login");
  };

  if (initialLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-50"><div className="h-8 w-8 animate-spin rounded-full border-4 border-slate-200 border-t-slate-800" /></div>;
  }

  if (!employee) return null;

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-10 border-b border-slate-100 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white"><Clock className="h-5 w-5" /></div>
            <div><h1 className="text-base font-semibold leading-tight text-slate-900">DestinLane</h1><p className="text-xs text-slate-500">Employee Attendance</p></div>
          </div>
          <button onClick={handleSignOut} className="text-sm font-medium text-slate-500 hover:text-slate-900">Sign out</button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3 }} className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <CheckInCard
              todayRecord={todayRecord}
              onLogin={() => startPunch("check-in")}
              onLogout={() => startPunch("check-out")}
              loading={loading}
              geoStatus={geoStatus}
              geoDistance={geoDistance}
              hasGeofence={hasGeofence}
            />
            <AttendanceSummary stats={stats} />
            <AttendanceCalendar records={records} />
            <AttendanceHistory records={records} />
          </div>
          <div className="space-y-6">
            <EmployeeProfile employee={employee} />
            <SalaryCard employee={employee} salaryRecords={salaryRecords} />
          </div>
        </motion.div>
      </main>

      <SelfieCapture
        open={selfieOpen}
        onOpenChange={setSelfieOpen}
        onConfirm={handleSelfieConfirm}
        busy={loading}
        punchTime={punchTime}
        coords={punchCoords}
        place={employee.site_name || null}
      />
    </div>
  );
}
