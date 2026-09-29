import React, { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { base44 } from "@/api/base44Client";
import { useToast } from "@/components/ui/use-toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  ArrowLeft,
  Server,
  Save,
  Plug,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Database,
  UploadCloud,
  DownloadCloud,
} from "lucide-react";

export default function ErpSettings() {
  const navigate = useNavigate();
  const { toast } = useToast();
  const [configId, setConfigId] = useState(null);
  const [form, setForm] = useState({
    api_base_url: "",
    api_key: "",
    employee_endpoint: "/employees",
    attendance_endpoint: "/attendance",
    auto_sync: false,
  });
  const [syncInfo, setSyncInfo] = useState({ last_sync_at: null, last_sync_status: "never", last_sync_message: "" });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [loading, setLoading] = useState(true);

  const loadConfig = useCallback(async () => {
    try {
      const configs = await base44.entities.ErpConfig.filter({}, "-updated_date", 1);
      if (configs.length > 0) {
        const c = configs[0];
        setConfigId(c.id);
        setForm({
          api_base_url: c.api_base_url || "",
          api_key: c.api_key || "",
          employee_endpoint: c.employee_endpoint || "/employees",
          attendance_endpoint: c.attendance_endpoint || "/attendance",
          auto_sync: c.auto_sync || false,
        });
        setSyncInfo({
          last_sync_at: c.last_sync_at,
          last_sync_status: c.last_sync_status || "never",
          last_sync_message: c.last_sync_message || "",
        });
      }
    } catch (e) {
      toast({ title: "Failed to load ERP config", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const handleSave = async () => {
    if (!form.api_base_url) {
      toast({ title: "API base URL is required", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      if (configId) {
        await base44.entities.ErpConfig.update(configId, form);
      } else {
        const created = await base44.entities.ErpConfig.create(form);
        setConfigId(created.id);
      }
      toast({ title: "ERP configuration saved" });
    } catch {
      toast({ title: "Failed to save", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await base44.functions.invoke("erpSync", { action: "test" });
      if (res.data?.ok) {
        toast({ title: "Connection successful", description: res.data.message });
      } else {
        toast({ title: "Connection failed", description: res.data?.error || "Unknown error", variant: "destructive" });
      }
    } catch (e) {
      toast({ title: "Connection failed", description: e.message, variant: "destructive" });
    } finally {
      setTesting(false);
    }
  };

  const handleSync = async (action) => {
    setSyncing(true);
    try {
      const res = await base44.functions.invoke("erpSync", { action });
      if (res.data?.ok !== false && !res.data?.error) {
        toast({ title: "Sync complete", description: res.data?.message || `Pulled ${res.data?.pulled || 0} employees, pushed ${res.data?.pushed || 0} records` });
        await loadConfig();
      } else {
        toast({ title: "Sync failed", description: res.data?.error || "Unknown error", variant: "destructive" });
      }
    } catch (e) {
      toast({ title: "Sync failed", description: e.message, variant: "destructive" });
    } finally {
      setSyncing(false);
    }
  };

  const statusConfig = {
    success: { icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50", label: "Last sync succeeded" },
    failed: { icon: AlertCircle, color: "text-rose-600", bg: "bg-rose-50", label: "Last sync failed" },
    never: { icon: AlertCircle, color: "text-slate-400", bg: "bg-slate-50", label: "Never synced" },
  };
  const sc = statusConfig[syncInfo.last_sync_status] || statusConfig.never;

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-10 border-b border-slate-100 bg-white/80 backdrop-blur-sm">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-5 py-4">
          <button onClick={() => navigate("/")} className="flex items-center gap-1.5 text-sm font-medium text-slate-500 hover:text-slate-900">
            <ArrowLeft className="h-4 w-4" />
            Back
          </button>
          <div className="ml-auto flex items-center gap-2">
            <Server className="h-5 w-5 text-slate-400" />
            <h1 className="text-base font-semibold text-slate-900">ERP Configuration</h1>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl space-y-6 px-5 py-8">
        {/* Connection Form */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm"
        >
          <div className="mb-5 flex items-center gap-2">
            <Database className="h-5 w-5 text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-700">ERP Connection</h2>
          </div>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="api_base_url">API Base URL</Label>
              <Input
                id="api_base_url"
                placeholder="https://erp.fortellus.com/api"
                value={form.api_base_url}
                onChange={(e) => setForm({ ...form, api_base_url: e.target.value })}
              />
              <p className="text-xs text-slate-400">The root URL of your ERP REST API</p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="api_key">API Key / Bearer Token</Label>
              <Input
                id="api_key"
                type="password"
                placeholder="Enter ERP API key"
                value={form.api_key}
                onChange={(e) => setForm({ ...form, api_key: e.target.value })}
              />
              <p className="text-xs text-slate-400">Sent as Authorization: Bearer &lt;key&gt; header</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="employee_endpoint">Employee Pull Endpoint</Label>
                <Input
                  id="employee_endpoint"
                  placeholder="/employees"
                  value={form.employee_endpoint}
                  onChange={(e) => setForm({ ...form, employee_endpoint: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="attendance_endpoint">Attendance Push Endpoint</Label>
                <Input
                  id="attendance_endpoint"
                  placeholder="/attendance"
                  value={form.attendance_endpoint}
                  onChange={(e) => setForm({ ...form, attendance_endpoint: e.target.value })}
                />
              </div>
            </div>

            <div className="flex items-center justify-between rounded-lg bg-slate-50 px-4 py-3">
              <div>
                <p className="text-sm font-medium text-slate-700">Auto-sync</p>
                <p className="text-xs text-slate-400">Automatically pull & push data on a schedule</p>
              </div>
              <Switch
                checked={form.auto_sync}
                onCheckedChange={(v) => setForm({ ...form, auto_sync: v })}
              />
            </div>
          </div>

          <div className="mt-6 flex gap-3">
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
              Save Configuration
            </Button>
            <Button variant="outline" onClick={handleTest} disabled={testing || !form.api_base_url}>
              {testing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Plug className="mr-2 h-4 w-4" />}
              Test Connection
            </Button>
          </div>
        </motion.div>

        {/* Sync Status & Actions */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="rounded-2xl border border-slate-100 bg-white p-6 shadow-sm"
        >
          <div className="mb-5 flex items-center gap-2">
            <RefreshCw className="h-5 w-5 text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-700">Data Sync</h2>
          </div>

          <div className={`mb-5 flex items-start gap-3 rounded-xl ${sc.bg} px-4 py-3`}>
            <sc.icon className={`mt-0.5 h-5 w-5 ${sc.color}`} />
            <div>
              <p className={`text-sm font-medium ${sc.color}`}>{sc.label}</p>
              {syncInfo.last_sync_at && (
                <p className="text-xs text-slate-500">
                  {new Date(syncInfo.last_sync_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                </p>
              )}
              {syncInfo.last_sync_message && (
                <p className="mt-0.5 text-xs text-slate-400">{syncInfo.last_sync_message}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Button variant="outline" onClick={() => handleSync("pull")} disabled={syncing}>
              <DownloadCloud className="mr-2 h-4 w-4" />
              Pull Employees
            </Button>
            <Button variant="outline" onClick={() => handleSync("push")} disabled={syncing}>
              <UploadCloud className="mr-2 h-4 w-4" />
              Push Attendance
            </Button>
            <Button onClick={() => handleSync("sync")} disabled={syncing}>
              {syncing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Sync All
            </Button>
          </div>

          <div className="mt-4 space-y-2 rounded-lg bg-slate-50 p-4 text-xs text-slate-500">
            <p className="font-medium text-slate-600">How it works:</p>
            <p>• <span className="font-medium">Pull Employees</span> — fetches employee master data from the ERP and updates local records (matched by phone number).</p>
            <p>• <span className="font-medium">Push Attendance</span> — sends the latest 500 attendance records (check-in/out, hours, status) to the ERP.</p>
            <p>• <span className="font-medium">Sync All</span> — runs both pull and push in sequence.</p>
          </div>
        </motion.div>
      </main>
    </div>
  );
}