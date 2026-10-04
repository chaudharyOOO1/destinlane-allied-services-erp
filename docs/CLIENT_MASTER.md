# Client Master

Client records include legal company name, GSTIN, PAN/CIN, billing address, regional branch, billing cycle and credit terms, primary/accounts contacts, services, contract summary dates and coordination notes. GSTIN and identifiers receive format validation; this is not external tax registration verification.

Codes C-DAS-0001 onward are allocated transactionally and cannot be edited. Duplicate GSTIN/company/portal links are rejected. Updates use versions to reject stale saves and retain history. Inactive clients retain their records.

Branch choices come from Company Profile. Coordinators must be active internal Staff Master operations/management personnel whose region and branch match. Assignment history remains stored. Optional active CLIENT portal accounts are linked one company per account. Client users can only read their linked company; internal create/edit remains administrator controlled.

Detailed contracts/rates and sites are subsequent action-list stages. No sample client or staff records are inserted into production.
