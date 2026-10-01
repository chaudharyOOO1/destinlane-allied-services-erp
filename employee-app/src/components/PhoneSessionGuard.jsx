import { Navigate, Outlet } from "react-router-dom";
import { getSession } from "@/lib/phoneSession";

export default function PhoneSessionGuard() {
  const session = getSession();
  const token = localStorage.getItem("emp_access_token");
  if (!session || !token) return <Navigate to="/login" replace />;
  return <Outlet />;
}
