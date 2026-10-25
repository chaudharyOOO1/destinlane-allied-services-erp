# Staff pay, employee wages and account access

## Approve staff pay for a month

1. Open **Payroll**, choose the month, and expand **Internal staff · monthly Management approval**.
2. Choose active staff. Confirm the staff member has a branch in Staff Master.
3. Enter the proposed gross amount, reviewed deductions and a note describing branch work and the calculation. Submit the proposal.
4. Management opens the proposal, selects Approve or Reject, enters a review note and confirms. Every month requires its own proposal and approval.
5. Revise a draft/rejected proposal if necessary. Approved/paid proposals are locked.
6. After making the payment externally, an authorised account selects Record payment and supplies the actual date and reference.

No salary is generated merely because staff are active. Payment recording does not send money. Figures and deduction treatment must be reviewed before approval.

## Configure deployed employee wages

Open Payroll → Employee wage setup. Choose the employee, effective date, daily wage and reason. Save a new rate for each change; historical rates cannot be overwritten. Configure wages before calculating attendance payroll. Client billing rates do not set employee wages.

A missing wage produces an explicit error. Finalised payroll cannot be recalculated or newly held. Employee statutory configuration and approval/payment workflows remain activation tasks before live employee payroll.

## Employee documents and payslips

Employees sign in to `/employee`. Documents displays verified files through short-lived private links. Reopen Documents if a link expires. Salary displays approved/disbursed slips; Download retrieves the branded backend PDF. Other employees' slips are inaccessible.

## Manage account access

Open User Management and select an account. Use the departmental role for standard access. Expand Custom permissions only for exceptions. Toggle the required actions, then select Save access once. Unsaved changes are labelled. Reload saved access discards local permission edits. If someone else changed the account, reload and review before saving again.

Creating an account is collapsed under Create account. For internal staff, use Staff Master so the DASS ID and ERP login remain linked. New/reset users change their temporary password on first sign-in. Five failed office sign-ins lock that account for fifteen minutes.

## Installed employee app

The web portal uses /employee. The Android package uses the same ERP backend over HTTPS, with local navigation and native camera/location permissions. Allow precise location when recording attendance. Actual camera/GPS/device acceptance must still be performed on a physical phone before rollout.
