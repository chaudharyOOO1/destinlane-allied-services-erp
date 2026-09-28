import { Navigate, Outlet } from "react-router-dom";
import { getSession } from "@/lib/phoneSession";

export default function PhoneSessionGuard() {
  const session = getSession();
  if (!session) return <Navigate to="/login" replace />;
  return <Outlet />;
}