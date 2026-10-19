# Company Money — MD user guide

Sign in as **DestinLane Administrator (ADMIN-001)** and open **Finance → Company Money**. This workspace is restricted to the designated MD account.

## Everyday recording

1. Choose **Money Out**, **Money In** or **Transfer**.
2. Enter the date and company bank/cash account. Select the business reason and category, who paid/received, amount, purpose and bank reference or bill number. For transfers, choose the destination company account.
3. Choose **Review record**. Check the summary; nothing has been saved yet.
4. Choose **Save draft**. Keep the MDJ reference. The draft is saved but excluded from reports.
5. Choose **Confirm and record** once the details are correct. The backend posts the balanced entry and reports include it. This records bookkeeping; it does not send a bank payment.

Use the reason that reflects the original transaction:

| Action | Choose | Effect |
| --- | --- | --- |
| Pay a new business expense | Money Out → Business expense | Records the expense and reduces bank/cash |
| Buy equipment | Money Out → Buy equipment or another asset | Increases the selected asset; no immediate expense |
| Pay a previously accrued supplier/payroll/loan balance | Money Out → Pay a supplier, loan or other amount owed | Reduces the liability; avoids expensing it twice |
| Receive payment for an existing invoice | Money In → Collect a client balance | Reduces the receivable; avoids recording revenue twice |
| Receive new income not already accrued | Money In → New business income | Records revenue |
| Receive borrowing or introduce capital | Money In → Receive a loan or advance / Capital introduced | Increases the chosen liability/equity, not revenue |
| Move funds between company accounts | Transfer | Moves bank/cash balances; no income or expense |

Choose the correct category account within each reason. Classification is not inferred from the bank narration. Tax splits, interest/principal splits, payroll accruals and other complex entries belong in **Advanced Accounting → Books**. Existing operational billing/payroll/travel records are not automatically imported into these books. Check for prior recognition before recording their payment.

**Recent records** lets you review the latest 200 entries. Saved drafts can be adjusted through **Adjust draft in Advanced**. Posted entries are immutable; correct them with a reasoned reversal and replacement in Advanced Accounting. Do not record a transfer twice when it appears on both statements.

## Bank Review

1. Choose a bank account and download the CSV template. Bank Review excludes cash accounts.
2. Use `statement_id,date,reference,description,debit,credit`, stable unique transaction IDs, YYYY-MM-DD dates and plain amounts. Debit means withdrawal; credit means deposit. Exclude opening-balance rows. Limit: 2 MiB / 5000 rows. Identical re-imports are skipped; conflicting IDs are rejected.
3. Upload the statement. Importing does not change the books.
4. If the transaction is already recorded, select its existing exact-amount match, checking date, party and reference, then choose **Match**.
5. If genuinely unbooked, choose **Record**. Bank, date, amount, narration and reference are filled in. Choose the reason/category and party, review, save and confirm. The workspace then attempts to match the new record to the originating bank row.
6. Enter the actual closing balance, date and statement reference, then **Check bank balance**. Review outstanding payments, deposits in transit and unbooked rows.

If recording succeeded but matching failed, the message says so. Return to Bank Review and match the **existing** posted record; do not record it again. Each statement/book line may match once. Removing a match requires a reason. Opening balances cannot be matched to transactions.

“Bank reconciled” requires zero difference, no unbooked imported rows and confirmed openings. You must still check statement completeness and classification. Book balances are not live bank feeds.

## Reports

Open **Reports** for bank/cash balances, business income, expenses, profit/loss, breakdowns and balance sheet. Blank From means current financial year; the balance sheet and bank balances remain cumulative through the To date. Choose **Update reports** after changing dates. **Download detailed reports** exports the trial balance, P&L and balance sheet as CSV. Open detailed accounting reports for individual ledgers, bank books and their exports.

Only posted records contribute. Transfers, capital, loans and settlements are not new business income/expense. Reports remain provisional until genuine openings are confirmed.

## Initial setup and accountant tools

Open **Advanced Accounting → Setup** to set the books start date, April–March year, company bank details and period locks. Additional accounts can be created here. Bank details do not connect to your bank.

Obtain the complete opening trial balance and bank reconciliation from your accountant. In **Books → New voucher**, choose Opening, use the books start date and enter the genuine opening debit/credit balances, then save and post. Confirm reconciled openings in Setup with a reason/reference. Genuine zero opening requires an explicit reason. Never invent a capital/equity balance to make entries balance. Ordinary recording is blocked until opening confirmation, but drafts can be prepared.

Advanced Accounting retains journals, tax arithmetic, general ledgers, bank reconciliation, full reports, audit history, reversals and period close/reopen. Dates/year policy lock after posting/import; drafts in a period block closing it. A lock does not perform annual profit closing. GST arithmetic does not determine tax treatment or eligibility.

## Recover safely

If saving succeeded but refresh failed, keep the displayed reference and reopen it; do not create it again. If a network timeout leaves the save outcome uncertain, refresh and inspect existing records before retrying. No automatic write retry is performed. Never share bank statements or private documents in support screenshots.

Have your accountant review openings, classifications, tax, accruals, depreciation and statutory schedules before statutory use. A zero balance check establishes arithmetic equality, not completeness or legal correctness.
