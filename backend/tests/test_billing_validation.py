"""Regression first: original unpatched invoice validation must fail."""
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from test_postgres_workflow import postgres_workflow, test_bootstrap_and_employee_to_invoice as bootstrap_invoice

def auth(http,user="TEST-OWNER"):
 r=http.post("/api/v1/auth/login",json={"login_id":user,"password":"local-test-password"})
 assert r.status_code==200, r.text
 return {"Authorization":"Bearer "+r.json()["access_token"]}

def test_invalid_client_identifiers_are_422_and_never_write(postgres_workflow):
 http,sessions,eng,today,*_=postgres_workflow
 hdr=auth(http)
 invalid=["INVALID-CLIENT-ID","1abc", "-1", -1, 0, True, [], {}, 0.2, "2.3", "9"*200]
 with TestClient(app, raise_server_exceptions=False) as safe:
  for raw in invalid:
   res=safe.post("/api/v1/erp/billing/generate",json={"month":today.strftime("%Y-%m"),"client_id":raw},headers=hdr)
   assert res.status_code==422,(repr(raw),res.status_code,res.text[:250])
 with sessions() as db:
  assert db.execute(text("select count(*) from invoices")).scalar_one()==0

def test_valid_optional_and_numeric_string_client_id_continue_to_work(postgres_workflow):
 http,sessions,eng,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
 hdr=auth(http)
 for data in [{"month":today.strftime("%Y-%m")},{"month":today.strftime("%Y-%m"),"client_id":None},{"month":today.strftime("%Y-%m"),"client_id":client_id},{"month":today.strftime("%Y-%m"),"client_id":str(client_id)}]:
  res=http.post("/api/v1/erp/billing/generate",json=data,headers=hdr)
  assert res.status_code==200,(data,res.status_code,res.text[:250])

def test_billing_invoice_generation_retrieval_and_idempotent_retry(postgres_workflow):
 bootstrap_invoice(postgres_workflow)
 http,sessions,eng,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
 hdr=auth(http)
 results=http.get("/api/v1/erp/billing/invoices",headers=hdr)
 assert results.status_code==200
 assert len(results.json())==1
 invoice=results.json()[0]
 assert invoice["status"]=="DRAFT"
 for _ in range(2):
  res=http.post("/api/v1/erp/billing/generate",json={"month":today.strftime("%Y-%m"),"client_id":client_id},headers=hdr)
  assert res.status_code==200 and res.json()["invoices_created"]==0,res.text
 with sessions() as db:
  assert db.execute(text("select count(*) from invoices")).scalar_one()==1


def test_parallel_invoice_generation_creates_exactly_one(postgres_workflow):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    bootstrap_invoice(postgres_workflow)
    http,sessions,eng,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    hdr=auth(http)
    with sessions() as db:
        db.execute(text("delete from invoices"))
        db.commit()
    barrier=Barrier(2)
    def issue():
        barrier.wait(timeout=8)
        with TestClient(app,raise_server_exceptions=False) as safe:
            res=safe.post("/api/v1/erp/billing/generate",json={"month":today.strftime("%Y-%m"),"client_id":client_id},headers=hdr)
        return res.status_code, (res.json() if res.status_code==200 else res.text[:300])
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(issue) for _ in range(2)]
        results=[f.result(timeout=18) for f in futures]
    assert [r[0] for r in results]==[200,200],results
    assert sorted(r[1]["invoices_created"] for r in results)==[0,1],results
    with sessions() as db:
        assert db.execute(text("select count(*) from invoices")).scalar_one()==1

