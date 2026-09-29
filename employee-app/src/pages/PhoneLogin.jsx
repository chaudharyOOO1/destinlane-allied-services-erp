import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { base44 } from "@/api/base44Client";
import { supabase } from "@/api/supabaseClient";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Phone, Loader2, Fingerprint, ArrowRight } from "lucide-react";
import { setSession } from "@/lib/phoneSession";

export default function PhoneLogin() {
  const navigate = useNavigate();
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e) => {
    e.preventDefault();
    const clean = phone.replace(/\D/g, "");
    if (clean.length < 10) {
      setError("Enter a valid phone number");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const { data: results, error } = await supabase
  .from("employees")
  .select("*")
  .eq("phone", clean);
      if (results.length > 0 && results[0].status !== "inactive") {
        setSession(results[0]);
        navigate("/");
      } else if (results.length > 0 && results[0].status === "inactive") {
        setError("Your account is inactive. Contact HR.");
      } else {
        setError("Phone number not registered with ERP");
      }
    } catch (err) {
      setError(err.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 via-white to-slate-100 p-4">
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="w-full max-w-md"
      >
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-900 text-white shadow-lg">
            <Fingerprint className="h-7 w-7" />
          </div>
          <h1 className="font-heading text-2xl font-semibold text-slate-900">
            Fortellus Allied Services
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            FAS · Employee Attendance — Login with your registered phone number
          </p>
        </div>

        <div className="rounded-3xl border border-slate-100 bg-white p-7 shadow-xl shadow-slate-200/40">
          {error && (
            <div className="mb-5 rounded-xl bg-rose-50 px-4 py-3 text-sm font-medium text-rose-600 ring-1 ring-rose-100">
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Phone Number</label>
              <div className="relative">
                <Phone className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
                <Input
                  type="tel"
                  inputMode="numeric"
                  autoFocus
                  placeholder="9876543210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="h-14 pl-12 text-lg tracking-wide"
                  required
                />
              </div>
              <p className="text-xs text-slate-400">No password needed — just your phone</p>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="h-14 w-full text-base font-semibold"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Verifying...
                </>
              ) : (
                <>
                  Continue
                  <ArrowRight className="ml-2 h-5 w-5" />
                </>
              )}
            </Button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-slate-400">
          Fortellus Allied Services Pvt Ltd (FAS)
        </p>
        <p className="mt-2 text-center text-[11px] font-medium text-slate-400">
          Powered by Fortelus Allied Services © 2026
        </p>
      </motion.div>
    </div>
  );
}
