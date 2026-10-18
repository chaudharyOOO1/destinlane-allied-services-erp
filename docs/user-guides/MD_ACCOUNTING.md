# MD bookkeeping — user guide

Sign in as **DestinLane Administrator (ADMIN-001)** and open **Finance → MD Books & Accounting**. Other logins do not have this workspace.

## 1. Set up the books

1. In **Setup**, choose the books start date and retain April as the financial-year starting month unless your accountant instructs otherwise.
2. Configure the Company Current Account ledger with the real bank details, or create a distinct bank ledger for each current account. These details do not connect to your bank.
3. Obtain the complete opening trial balance and bank reconciliation from your accountant. In **Books → New voucher**, choose Opening, enter the start date and the genuine opening debit/credit balances, then save and post.
4. Confirm reconciled opening balances in Setup with a reason/reference. Use zero opening only if the business actually has zero opening balances. **Do not invent a capital or equity balance just to make an entry balance.**

Ordinary vouchers cannot be posted before opening confirmation. Dates/year policy lock once records are posted or statements imported.

## 2. Record every payment and receipt

Use the **Payment / receipt helper** to select the company bank, correct counter-account and full amount, then prepare a balanced draft. Complete the date, party/payee, bank or voucher reference, business purpose and line details.

- Payment: debit the correct expense/asset/payable and credit Bank.
- Receipt: debit Bank and credit the correct income/receivable/loan/capital account.
- Transfer between your own cash/bank accounts: use Contra.
- Tax splits, salary accrual and other adjustments: use multiple lines in Journal.

Choose **Save voucher draft**, review equal debits/credits, then **Post balanced voucher**. Drafts do not enter reports. Record a bank transfer only once in the books. Paying an existing creditor/payroll liability is a liability settlement, not a second expense.

Example service invoice including GST: Dr Receivable ₹1,180; Cr Service Revenue ₹1,000; Cr Output GST ₹180. On collection: Dr Bank ₹1,180; Cr Receivable ₹1,180. This keeps tax out of revenue and avoids counting collections twice.

The ERP records bookkeeping; it does not send bank payments. Existing Travel/Payroll/Billing records are not silently imported into these books. Link them through accurate voucher references and check for prior accrual before booking payment.

## 3. Import and match your bank statement

1. Open **Bank reconciliation**, select the bank and download the CSV template.
2. Convert the bank statement to `statement_id,date,reference,description,debit,credit`. Use stable unique transaction IDs, YYYY-MM-DD dates and plain amounts. Debit means bank withdrawal; credit means bank deposit. Do not include the opening-balance row.
3. Import the CSV (maximum 2 MiB / 5000 rows). Re-importing the same IDs/data safely skips them; changed data under an existing ID is rejected for review.
4. For an unbooked row, select **Prepare voucher**, choose the appropriate counter-account, complete party/details, save and post.
5. Return to Bank reconciliation, select the corresponding posted bank line and **Match**. Check reference/date as well as amount. Opening balance lines cannot be matched as transactions.
6. Enter the actual statement closing balance and date/reference; calculate reconciliation. Review outstanding payments, deposits in transit and unbooked transactions.

RECONCILED requires zero difference, no unbooked imported rows and confirmed openings. You still must ensure the statement is complete and classifications are correct. Imported rows alone do not change P&L or the bank ledger.

## 4. Review records and reports

- **Books → General ledger / bank book:** select an account and view/export every posted transaction with reference, payee, debit, credit and running balance. It uses the Reports date range; blank start means books start.
- **Reports:** select the P&L start/end or leave start blank for current FY, then refresh. Review trial balance, P&L and the cumulative balance sheet; export financial reports CSV.
- **Audit:** inspect setup/account changes, imports, matches, posting/reversal, exports, period-lock decisions and reconciliation snapshots.

Balance-sheet profit includes current FY and prior unclosed earnings; a period lock does not automatically perform annual closing. GST arithmetic is a helper only: your accountant must confirm the rate, supply treatment and eligibility before making tax entries.

## 5. Correct errors safely

Draft: reopen, edit and save. Posted voucher: use **Reverse posted voucher** with the correct open date and explanation, then post a corrected voucher. The original remains. A voucher can be reversed once.

Lock a reconciled period in Setup with a reason. Closing is blocked while drafts exist in that period. Reducing/clearing the lock reopens it and is audited.

If a save/response is uncertain, inspect the existing voucher before retrying. If a write succeeded but refresh failed, retain its voucher/reference and reopen; do not create it again. Never share bank numbers, statements or signed documents in support screenshots.

These are management books. Your accountant must review classifications, openings, liabilities/tax, depreciation, statutory schedules and filings before statutory use. A zero trial/balance-sheet difference proves arithmetic balance, not completeness or legal correctness.
