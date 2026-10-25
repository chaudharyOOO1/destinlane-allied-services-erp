"""DestinLane hosted DEVELOPMENT Auth/storage integration probe.

Never targets production. Default --plan is offline. Live read-only checks
require --preflight and a dev-only service-role secret. Mutations require
--execute and an explicit approval variable. It creates solely disposable
fictional Auth users and test-prefix storage objects, then deletes them.
ERP application API mutations are intentionally excluded until a dev backend
preview and synthetic ERP role fixtures have been approved separately.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from uuid import uuid4

DEV_REF = "ahyjvxebhokclmmxrdxc"
DEV_URL = f"https://{DEV_REF}.supabase.co"
PROD_REF = "zvogktuqdcpjsfargewg"
APPROVAL = "ERP-DEV-001"
BUCKETS = (
    "employee-documents",
    "employee-selfies",
    "travel-expense-receipts",
    "company-legal-documents",
)
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4"
    "z8DwHwAFgAI/ScL/nwAAAABJRU5ErkJggg=="
)
PDF = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
       b"2 0 obj<</Type/Pages/Count 0/Kids[]>>endobj\n"
       b"trailer<</Root 1 0 R>>\n%%EOF\n")


@dataclass
class Evidence:
    checks: dict[str, str] = field(default_factory=dict)
    cleanup_errors: list[str] = field(default_factory=list)

    def record(self, key: str, value: str):
        self.checks[key] = value
        print(f"{key}: {value}")

    def finish(self):
        print("SUMMARY:", json.dumps({
            "environment": "destinlane-erp-development",
            "project_ref": DEV_REF,
            "checks": self.checks,
            "cleanup_errors": self.cleanup_errors,
        }, sort_keys=True))
        return not self.cleanup_errors


class Client:
    def __init__(self, key: str):
        if not key or len(key) < 16:
            raise ValueError("Development-only service role key required in environment.")
        self.key = key

    def call(self, path: str, method="GET", *, payload=None,
             content_type="application/json", statuses=(200,)):
        path = "/" + path.lstrip("/")
        if "://" in path or ".." in path:
            raise ValueError("Invalid relative API path")
        data = None
        if payload is not None:
            data = json.dumps(payload).encode() if isinstance(payload, (dict,list)) else payload
        headers = {"apikey": self.key, "Authorization": "Bearer " + self.key,
                   "Content-Type": content_type}
        request = urllib.request.Request(DEV_URL + path, data=data,
                                         headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=16) as response:
                raw=response.read()
                if response.status not in statuses:
                    raise RuntimeError(f"HTTP {response.status} for {method} {path}")
                if raw and response.headers.get("Content-Type", "").startswith("application/json"):
                    return json.loads(raw)
                return raw
        except urllib.error.HTTPError as exc:
            if exc.code in statuses:
                return {"_http_status": exc.code}
            # Do not include response bodies; they may contain tokens or PII.
            raise RuntimeError(f"HTTP {exc.code} for {method} {path}") from None
        except urllib.error.URLError:
            raise RuntimeError(f"Unable to reach dev service for {method} {path}") from None


def guard_env():
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if url != DEV_URL or PROD_REF in url:
        raise SystemExit("STOP: SUPABASE_URL must be the exact dedicated development project URL.")
    if (other := os.environ.get("ERP_DEV_API_BASE_URL")):
        host=urllib.parse.urlsplit(other).hostname or ""
        if (not host or PROD_REF in other or host == "erp.destinlane.in"
            or "destinlane-allied-services-20t0ol0wg" in host):
            raise SystemExit("STOP: ERP_DEV_API_BASE_URL resembles production.")
    return Client(os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))


def preflight(client: Client, evidence: Evidence):
    # Pure GET requests; no user/data mutation.
    result = client.call("/auth/v1/admin/users?per_page=1&page=1")
    if not isinstance(result, dict) or not isinstance(result.get("users"), list):
        raise RuntimeError("Auth admin read-only check returned unexpected response")
    evidence.record("auth_admin_read", "PASS")
    for bucket in BUCKETS:
        status=client.call("/storage/v1/bucket/" + bucket)
        if not isinstance(status, dict) or status.get("public") is not False:
            raise RuntimeError(f"Bucket {bucket} absent or public")
        evidence.record("bucket_" + bucket, "PRIVATE / PRESENT")
    dev_api = os.environ.get("ERP_DEV_API_BASE_URL", "").rstrip("/")
    if dev_api:
        request=urllib.request.Request(dev_api + "/health", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                check=json.load(response)
                if response.status != 200 or check.get("status") != "healthy":
                    raise RuntimeError("Dev backend health check failed")
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
            raise RuntimeError("Development backend health check unavailable") from None
        evidence.record("dev_api_health", "PASS / READ ONLY")


def write_checks(client: Client, evidence: Evidence):
    if os.environ.get("DESTINLANE_QA_APPROVAL") != APPROVAL:
        raise SystemExit("STOP: Lead developer must authorize ERP-DEV-001.")
    if os.environ.get("DESTINLANE_QA_ALLOW_MUTATIONS") != "true":
        raise SystemExit("STOP: DESTINLANE_QA_ALLOW_MUTATIONS must equal true.")
    run=uuid4().hex
    email="qa-destinlane-"+run+"@example.com"
    password=secrets.token_urlsafe(30)
    user_id=None
    uploaded=[]
    try:
        user=client.call("/auth/v1/admin/users", method="POST", statuses=(200,201),
                         payload={"email":email,"password":password,"email_confirm":True,
                                  "app_metadata":{"destinlane_qa_run":run}})
        user_id=user.get("id") if isinstance(user,dict) else None
        if not user_id:
            raise RuntimeError("Auth user created without expected identifier")
        remote=client.call("/auth/v1/admin/users/"+user_id)
        if remote.get("email","").lower()!=email.lower():
            raise RuntimeError("Auth user readback mismatch")
        evidence.record("auth_admin_create_readback", "PASS")
        token=client.call("/auth/v1/token?grant_type=password",method="POST",
                          statuses=(200,),payload={"email":email,"password":password})
        if not isinstance(token,dict) or not token.get("access_token"):
            raise RuntimeError("Auth sign-in did not return access token")
        evidence.record("auth_signin", "PASS")
        # A repeated creation must not modify the account already created.
        duplicate=client.call("/auth/v1/admin/users",method="POST", statuses=(400,409,422),
                              payload={"email":email,"password":secrets.token_urlsafe(30),
                                       "email_confirm":True})
        if duplicate.get("_http_status") not in (400,409,422):
            raise RuntimeError("Duplicate Auth create unexpectedly succeeded")
        evidence.record("auth_duplicate_rejected", "PASS")
        for bucket,content,mime in (
            ("employee-documents",PNG,"image/png"),
            ("employee-selfies",PNG,"image/png"),
            ("travel-expense-receipts",PDF,"application/pdf"),
        ):
            object_path=f"qa-releases/{run}/{bucket}.{'pdf' if mime.endswith('pdf') else 'png'}"
            rel="object/"+bucket+"/"+urllib.parse.quote(object_path,safe="/")
            client.call("/storage/v1/"+rel,method="POST",payload=content,
                        content_type=mime,statuses=(200,201))
            uploaded.append((bucket,object_path))
            signed=client.call("/storage/v1/object/sign/"+bucket+"/"+
                urllib.parse.quote(object_path,safe="/"),
                method="POST",payload={"expiresIn":60},statuses=(200,201))
            if not isinstance(signed,dict) or not (
                signed.get("signedURL") or signed.get("signedUrl")):
                raise RuntimeError("Storage signed URL not returned")
            signed_path = signed.get("signedURL") or signed.get("signedUrl")
            if signed_path.startswith("https://"):
                signed_url = signed_path
            elif signed_path.startswith("/storage/v1/"):
                signed_url = DEV_URL + signed_path
            else:
                signed_url = DEV_URL + "/storage/v1/" + signed_path.lstrip("/")
            if urllib.parse.urlsplit(signed_url).hostname != f"{DEV_REF}.supabase.co":
                raise RuntimeError("Signed download URL is outside the development project")
            with urllib.request.urlopen(signed_url,timeout=15) as readback:
                downloaded=readback.read(len(content)+1)
                if readback.status!=200 or downloaded!=content:
                    raise RuntimeError("Private storage signed download/readback mismatch")
            evidence.record("private_storage_"+bucket, "UPLOAD + SIGN + DOWNLOAD PASS")
    finally:
        for bucket,path in reversed(uploaded):
            try:
                client.call("/storage/v1/object/"+bucket+"/"+
                            urllib.parse.quote(path,safe="/"), method="DELETE",
                            statuses=(200,204))
                evidence.record("cleanup_storage_"+bucket, "PASS")
            except Exception:
                evidence.cleanup_errors.append(f"storage:{bucket}/qa-releases/<run>")
        if not user_id:
            # A response could be lost after remote creation; find only this
            # run's server-owned marker rather than deleting arbitrary users.
            try:
                users=client.call("/auth/v1/admin/users?per_page=100&page=1")
                matched=[u for u in users.get("users",[]) if u.get("email")==email
                         and u.get("app_metadata",{}).get("destinlane_qa_run")==run]
                if len(matched)==1:
                    user_id=matched[0].get("id")
            except Exception:
                evidence.cleanup_errors.append("possible_auth_orphan:<redacted>")
        if user_id:
            try:
                client.call("/auth/v1/admin/users/"+user_id,method="DELETE",
                            statuses=(200,204))
                evidence.record("cleanup_test_auth_user", "PASS")
            except Exception:
                evidence.cleanup_errors.append("auth_user:<redacted-id>")


def authenticated_dev_api_smoke(evidence: Evidence):
    """Optional read-only ERP API workflows against a distinct dev preview."""
    if os.environ.get("DESTINLANE_QA_APPROVAL") != "ERP-DEV-002":
        raise RuntimeError("ERP-DEV-002 approval required for authenticated API probe")
    base=os.environ.get("ERP_DEV_API_BASE_URL","").rstrip("/")
    login_id=os.environ.get("ERP_DEV_TEST_LOGIN_ID")
    password=os.environ.get("ERP_DEV_TEST_PASSWORD")
    if not base or not login_id or not password:
        raise RuntimeError("Dev backend preview and synthetic ERP test account required")
    # guard_env already checked production URL exclusions.
    def api_request(path,method="GET",payload=None,token=None):
        data=json.dumps(payload).encode() if payload is not None else None
        headers={"Content-Type":"application/json"}
        if token:
            headers["Authorization"]="Bearer "+token
        req=urllib.request.Request(base+"/api/v1"+path,headers=headers,
                                   data=data,method=method)
        try:
            with urllib.request.urlopen(req,timeout=16) as response:
                if response.status!=200:
                    raise RuntimeError("Unexpected development API HTTP status")
                raw=response.read()
                return json.loads(raw) if raw else {}
        except (urllib.error.HTTPError,urllib.error.URLError,ValueError):
            raise RuntimeError("Development API authentication/read failed at "+path) from None
    result=api_request("/auth/login",method="POST",
                       payload={"login_id":login_id,"password":password})
    token=result.get("access_token")
    if not token:
        raise RuntimeError("Development ERP login did not return a token")
    evidence.record("dev_erp_login","PASS")
    for path in (
        "/auth/me",
        "/erp/internal-staff",
        "/erp/employees/workflow/intimations",
        "/erp/travel-expenses",
        "/erp/clients",
    ):
        api_request(path,token=token)
        evidence.record("api_"+path.replace("/","_").strip("_"),"PASS / AUTHENTICATED GET")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--plan",action="store_true",help="Offline plan (default); no network")
    group.add_argument("--preflight",action="store_true",help="Read-only hosted dev checks")
    group.add_argument("--execute",action="store_true",help="ERP-DEV-001: disposable dev Auth/storage writes")
    group.add_argument("--api",action="store_true",help="ERP-DEV-002: synthetic dev ERP login + read-only API")
    args=parser.parse_args()
    if not (args.preflight or args.execute or args.api):
        print("DEV PROJECT:",DEV_REF)
        print("PLAN: Auth admin read + four private storage bucket GETs.")
        print("EXPLICIT WRITE APPROVAL:",APPROVAL)
        print("AFTER APPROVAL: disposable Auth creation/signin/duplicate + three private storage upload/sign/delete checks.")
        print("NO LIVE TEST EXECUTED; NO PRODUCTION ENVIRONMENT PERMITTED.")
        print("ERP-DEV-002: authenticated login/read-only API requires approved dev preview and synthetic test owner.")
        print("Full ERP API business mutation UAT requires a further approved isolated fixture plan.")
        return 0
    evidence=Evidence()
    client=guard_env()
    try:
        preflight(client,evidence)
        if args.execute:
            write_checks(client,evidence)
        if args.api:
            authenticated_dev_api_smoke(evidence)
        return 0 if evidence.finish() else 3
    except Exception as exc:
        # Suppress actual API bodies/headers and any secrets.
        evidence.record("gate",f"BLOCKED: {type(exc).__name__}")
        evidence.finish()
        return 2

if __name__ == "__main__":
    sys.exit(main())
