# Company identity and printed invoices

`frontend/src/components/CompanyLogo.jsx` is shared by the sign-in page, workspace shell and invoice preview. It preserves image proportions, handles a missing or failed logo image and renders a text wordmark as the fallback. The DAS initials used by that fallback and the browser icon are text identity, not a recreation of the company's official logo.

## Installing the approved logo

The approved logo was supplied as a chat image during this work. The original image file was not available in the execution workspace at implementation time. Until that asset can be downloaded or attached as a usable file, the interface uses the wordmark fallback.

1. Obtain the original, approved PNG, WebP or SVG. Prefer a transparent background and a legible dark-on-light variant. Do not substitute a stock shield or redraw the trademark.
2. Save it in `frontend/public/company-logo.png` (or the correct extension for the supplied file).
3. Set `VITE_COMPANY_LOGO_URL=/company-logo.png` in the frontend build environment, then rebuild and deploy. This is a public asset path, not a credential. An approved HTTPS logo URL also works, subject to its server availability and browser access policy.
4. Replace `frontend/public/favicon.svg` with a suitable approved small-icon asset if provided. The current DAS text icon deliberately replaces the unrelated Vite template icon.
5. Check the login, expanded and collapsed sidebar, narrow mobile layout and printed invoice. Ensure the image is not stretched or clipped. A failed image must leave the company name readable.

`CompanyLogo` accepts `compact`, `className`, `name`, `subtitle`, `logoUrl` and `imageClassName`. Use the live company profile for the legal name in business documents. The default public sign-in identity is DestinLane Allied Services Pvt Ltd.

## Invoice presentation

The browser invoice preview uses the recorded invoice number, client, billing month, issue/due dates, subtotal, tax rate, tax amount and total. Company address, GSTIN and contact details come from the company profile; missing values are omitted. A zero tax rate remains zero. The layout does not invent payment terms, bank details, detailed deployment descriptions, a signature exemption or digital-verification claims.

`company-branding.css` isolates `.invoice-print-sheet` for browser printing and resets its modal ancestors to prevent clipping. Other page content and invoice action buttons are excluded from print. Company-profile loading or failure disables the print action. This work does not change backend-generated PDFs, invoice calculations, statutory treatment or invoice data. The present invoice API supplies an aggregate services amount; it does not supply a detailed item or GST component breakdown. Obtain accountant review before treating the print layout as a complete statutory invoice for a particular transaction.

## Sign-in behavior

The form keeps the existing login API, recovery redirect and first-password-change behavior. Login IDs are trimmed; passwords are passed unchanged. Inputs have associated labels, username/current-password autocomplete, a pending state and an accessible failure message. No role selector, sample credentials or invented business statistics appear on the sign-in page.
