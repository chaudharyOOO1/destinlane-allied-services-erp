# Travel Expenses — user guide

The feature is prepared locally; it is not on the live ERP until its database migration and release are completed.

## Submit your travel expenses

1. Open **Finance → Travel Expenses → New travel claim**.
2. Enter the business purpose, From/To locations and travel dates. Select an existing company branch if applicable.
3. Add Transport, Lodging, Meals or Other expense items. Enter each date, description, amount in INR and bill/ticket number where available. Item dates must fall within the trip dates.
4. Select **Save travel draft**. Note the TRAVEL reference shown on the saved record.
5. Attach PDF/JPG/PNG receipts, up to 3 MiB each and ten per claim. If receipts are unavailable, enter an explanation and save it. Receipts are retained; check files before attaching.
6. After travel has ended and all edits are saved, select **Submit travel claim**. The claim is locked for review.
7. Follow its status in **My claims**. If rejected, read the remarks, edit and save the same claim, then resubmit. Do not create a replacement claim for the same trip.

## Approve or reject

Management, IT Super Admin and HR:

1. Change **Claims** to **All claims / approval and payment queue**; filter Status to **SUBMITTED**.
2. Open a claim and check the trip, item amounts and receipts or missing-receipt explanation.
3. Select **Approve claim**, or enter remarks and select **Reject with remarks**.

You cannot review your own claim. Another eligible reviewer must handle it.

## Record reimbursement

Accounts, Management and IT Super Admin:

1. Use the all-claims queue and filter Status to **APPROVED**.
2. Open the claim and confirm the full amount has actually been paid through your usual payment process.
3. Enter the payment date and bank/cash voucher reference, then select **Record reimbursement** once.
4. Check the **PAID** status and reference. The system adds one Travel expense to Accounts automatically; do not enter it again as a manual expense.

This button records payment; it does not send money. Partial payments and advances are not supported. A different authorised person must record your own reimbursement.

## Problems and recovery

- **Saved, but the directory could not refresh:** your claim/action was saved. Keep its reference; refresh the list rather than creating it again.
- **Claim changed:** reopen it, compare the latest version and reapply intended edits.
- **Unable to confirm / connection lost:** inspect My claims/the existing record before retrying. Ask the administrator if payment status is unclear.
- **Receipt storage unavailable:** no upload is confirmed. Retry when storage is restored. Submit an explanation only if receipts are genuinely unavailable under your company policy.
- **Submit/Attach disabled:** save unsaved claim edits first, or wait for the current action to finish.
- **Payment date rejected:** it must be on/after approval and no later than today. Contact Accounts if a historical payment needs reconciliation.

The directory shows the latest 200 matching claims and warns when more exist; filter by status. Draft input is not an offline backup. Keep passwords, signed receipt links, bank details and personal documents out of support screenshots.
