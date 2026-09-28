import { jsPDF } from "jspdf";

export function generateSalarySlip(employee, salary) {
  const doc = new jsPDF({ unit: "mm", format: "a4" });
  const pageW = doc.internal.pageSize.getWidth();
  const left = 18;
  let y = 20;

  // Header band
  doc.setFillColor(15, 23, 42);
  doc.rect(0, 0, pageW, 28, "F");
  doc.setTextColor(255, 255, 255);
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.text("SALARY SLIP", left, 14);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.text(`Pay Period: ${salary.month}`, pageW - left, 14, { align: "right" });
  doc.text("Fortellus Allied Services Pvt Ltd (FAS)", left, 21);

  y = 40;
  doc.setTextColor(15, 23, 42);

  // Employee details
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text("Employee Details", left, y);
  y += 7;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  const rows = [
    ["Name", employee.name || "—"],
    ["Employee Code", employee.employee_code || "—"],
    ["Designation", employee.designation || "—"],
    ["Date of Joining", employee.doj ? formatDate(employee.doj) : "—"],
    ["Assigned Site", employee.assigned_site || "—"],
    ["Bank", employee.bank_name || "—"],
    ["Account No.", employee.account_number || "—"],
  ];
  rows.forEach(([label, val]) => {
    doc.setTextColor(100, 116, 139);
    doc.text(label, left, y);
    doc.setTextColor(15, 23, 42);
    doc.text(String(val), left + 45, y);
    y += 6;
  });

  y += 6;
  doc.setDrawColor(226, 232, 240);
  doc.line(left, y, pageW - left, y);
  y += 8;

  // Attendance summary
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text("Attendance Summary", left, y);
  y += 7;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  const attRows = [
    ["Total Working Days", String(salary.work_days ?? "—")],
    ["Days Present", String(salary.present_days ?? "—")],
    ["Late Logins", String(salary.late_days ?? "—")],
    ["Leaves Taken", String(salary.leave_days ?? "—")],
    ["Days Absent", String(salary.absent_days ?? "—")],
  ];
  attRows.forEach(([label, val]) => {
    doc.setTextColor(100, 116, 139);
    doc.text(label, left, y);
    doc.setTextColor(15, 23, 42);
    doc.text(val, left + 55, y);
    y += 6;
  });

  y += 6;
  doc.setDrawColor(226, 232, 240);
  doc.line(left, y, pageW - left, y);
  y += 8;

  // Salary + status
  doc.setFont("helvetica", "bold");
  doc.setFontSize(12);
  doc.text("Payment Details", left, y);
  y += 7;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(10);
  doc.setTextColor(100, 116, 139);
  doc.text("Monthly Salary", left, y);
  doc.setTextColor(15, 23, 42);
  doc.setFont("helvetica", "bold");
  doc.text(`Rs. ${Number(salary.amount).toLocaleString("en-IN")}`, left + 55, y);
  y += 8;

  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.setTextColor(100, 116, 139);
  doc.text("Payment Status", left, y);
  if (salary.status === "credited") {
    doc.setTextColor(22, 163, 74);
    doc.text("CREDITED", left + 55, y);
    if (salary.credited_date) {
      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.text(`on ${formatDateTime(salary.credited_date)}`, left + 80, y);
    }
  } else {
    doc.setTextColor(217, 119, 6);
    doc.text("PENDING", left + 55, y);
  }

  // Footer
  y = doc.internal.pageSize.getHeight() - 20;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(148, 163, 184);
  doc.text("This is a system-generated salary slip and does not require a signature.", left, y);
  doc.text(`Generated on ${formatDateTime(new Date().toISOString())}`, left, y + 5);

  doc.save(`SalarySlip_${employee.name || "Employee"}_${salary.month}.pdf`);
}

function formatDate(d) {
  return new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(iso) {
  return new Date(iso).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}