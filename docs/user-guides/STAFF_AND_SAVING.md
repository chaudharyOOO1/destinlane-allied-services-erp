# Staff Master and saving — user guide

Audience: IT Super Admin, Management and authorised HR. This describes the local improvement; deployment and production acceptance are pending.

## Create a staff member

1. Sign in and open **Staff Master**.
2. Select **Add staff**.
3. Enter full name, mobile, email, department and designation. Choose an existing branch if applicable; complete optional employment details.
4. Choose the departmental role and working permissions. Grant only access required for the job; employee creation uses **Employees · create**.
5. Set a temporary password of at least 12 characters. Share it with the intended staff member through your approved private channel.
6. Select **Create staff and login** once and wait for the result.
7. Record the assigned **DASS** ID. The person uses that login and must change the password at first sign-in.

Ordinary staff cannot create other staff. Employee records use DASE IDs and their separate joining workflow.

## Edit details or access

Open the staff record, change the required details and select **Save staff details**. ERP role, permissions and login status are saved separately through **Save ERP access**. Linked login email and issued IDs cannot be edited through the staff form.

For status changes, enter a reason. Marking inactive or terminating disables login. After reactivation, explicitly enable login if appropriate. Termination retains the record and makes it read-only.

## Understand saving messages

| Message/situation | What to do |
|---|---|
| Saved with a staff ID | Creation succeeded. Use the existing record for further changes. |
| Saved, but record/directory could not refresh | The write succeeded. Do not create the person again. Reopen/refresh when connectivity returns and verify access. |
| Validation error | Correct the highlighted/reported details and save again. Entered values remain available in the current form. |
| Record changed/version conflict | Note intended edits, reopen the latest record, compare and reapply changes. |
| Timeout, lost connection or uncertain result | Search by name/mobile/ID first. Ask an administrator to check before retrying creation. |

Closing/reloading a page can discard unsaved input; retained form values are not a server-side draft or an offline backup. Never include passwords, Aadhaar, bank information or tokens in a support screenshot. For a saving issue, report the screen, approximate time, action and error text.
