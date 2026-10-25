# DestinLane employee portal

The active application uses the ERP FastAPI backend for phone/PIN login, attendance, private documents and approved payslips. `base44/` contains historical, unmounted reference files; the active app has no Base44 SDK dependency.

## Web development

Use Node 22.12+ and the backend's Python/PostgreSQL setup. Start the backend on port 8000, then:

```sh
npm ci
npm run test:runtime
npm run dev
```

Open the Vite URL under `/employee/`. The development server proxies `/api` to `http://127.0.0.1:8000`; `EMPLOYEE_DEV_API_ORIGIN` can select another local backend. Production web requests use the same ERP origin. Never put service credentials in a `VITE_` setting or test against production business data.

Validation: `npm run lint`, `npm run build`. Output goes to `dist/`; source assets are preserved. The lockfile supports npm 10 and npm 11.

## Installed Android app

```sh
npm ci
npm run test:runtime
npm run build:native
npx cap add android
node scripts/configure-android.mjs
npx cap sync android
```

Run `cap add android` only for a new generated Android project. Subsequent builds use `cap sync android`. Compile with Java 21 and the Android SDK, or use the repository's Android build workflow. Its artifact is `destinlane-employee-app-debug-apk`; a debug build is not a signed store release.

Native builds use relative assets, hash navigation and `https://erp.destinlane.in/api/v1` by default. `VITE_ERP_API_BASE_URL` can configure a different HTTPS ERP endpoint; never include credentials/query tokens. The legacy application ID remains for upgrade compatibility; the display name is DestinLane Employee.

The native camera/location plugins and Android permission declarations are configured. Physical camera, precise GPS, boundary rejection, device binding, overnight shifts and payslip downloads still require real-phone acceptance. Do not infer device readiness from APK compilation alone.

## Workflow and handover

- [Functional rules](../docs/functional/PAYROLL_AND_ACCESS_RELIABILITY.md)
- [User guide](../docs/user-guides/PAYROLL_AND_ACCESS.md)
- [Current development/readiness ledger](../docs/engineering/DEVELOPMENT_20261025.md)
- [Contributor rules](../AGENTS.md)

Staff DASS accounts use the office ERP. Approved deployed employees use phone/PIN attendance access. Do not create a second identity store or bypass joining approval. The approved logo PNG is pending; current DAS text is a wordmark placeholder.
