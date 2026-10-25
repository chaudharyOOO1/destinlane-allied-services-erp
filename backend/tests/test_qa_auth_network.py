"""Network-level Supabase Admin API contract emulation.

This uses real urllib HTTP requests to a LOCAL stub, not a hosted Supabase
project. It verifies failure/ambiguous-success behavior without live users.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from uuid import uuid4
from contextlib import contextmanager

from sqlalchemy import text
from test_postgres_workflow import postgres_workflow
from test_idempotent_write_retries import login, staff_body, STAFF
from app.core.config import settings
from app.models.internal_staff import StaffCodeCounter, StaffApprovalSettings

class State:
    def __init__(self):
        self.records={}
        self.requests=[]
        self.fail_created_response_once=False
        self.force_denial=False
        self.lock=threading.Lock()

@contextmanager
def local_auth_server(state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def answer(self,status,obj):
            content=json.dumps(obj).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        def do_POST(self):
            if urlsplit(self.path).path!='/auth/v1/admin/users': return self.answer(404,{})
            size=int(self.headers.get('Content-Length','0'))
            data=json.loads(self.rfile.read(size))
            with state.lock:
                state.requests.append(('POST',data.get('email')))
                if state.force_denial or self.headers.get('apikey')!='qa-remote-key':
                    return self.answer(401,{'message':'Unauthorized'})
                email=data['email'].lower()
                if email in state.records:
                    return self.answer(422,{'message':'User already registered'})
                item={'id':str(uuid4()),'email':email,'app_metadata':data.get('app_metadata',{})}
                state.records[email]=item
                if state.fail_created_response_once:
                    state.fail_created_response_once=False
                    return self.answer(503,{'message':'Simulated lost acknowledgement AFTER remote creation'})
                return self.answer(201,item)
        def do_GET(self):
            if urlsplit(self.path).path!='/auth/v1/admin/users': return self.answer(404,{})
            with state.lock:
                state.requests.append(('GET','list'))
                return self.answer(200,{'users':list(state.records.values())})
        def do_PUT(self):
            if not self.path.startswith('/auth/v1/admin/users/'): return self.answer(404,{})
            size=int(self.headers.get('Content-Length','0'))
            data=json.loads(self.rfile.read(size))
            with state.lock:
                state.requests.append(('PUT',self.path.rsplit('/',1)[-1]))
                for item in state.records.values():
                    if item['id']==self.path.rsplit('/',1)[-1]:
                        return self.answer(200,item)
                return self.answer(404,{})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    th=threading.Thread(target=server.serve_forever,daemon=True)
    th.start()
    try: yield f'http://127.0.0.1:{server.server_address[1]}'
    finally:
        server.shutdown()
        server.server_close()
        th.join(timeout=2)

def staff_db_prep(sessions):
    with sessions() as db:
        if db.get(StaffCodeCounter, 1) is None:
            db.add(StaffCodeCounter(id=1,next_number=10))
        if db.get(StaffApprovalSettings, 1) is None:
            db.add(StaffApprovalSettings(id=1,version=1))
        db.commit()

def test_real_http_auth_ambiguous_remote_success_recovers_without_local_duplicates(postgres_workflow,monkeypatch):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    staff_db_prep(sessions)
    state=State()
    state.fail_created_response_once=True
    authenticated=login(http,'TEST-OWNER')
    with local_auth_server(state) as url:
        monkeypatch.setattr(settings,'SUPABASE_URL',url)
        monkeypatch.setattr(settings,'SUPABASE_SERVICE_ROLE_KEY','qa-remote-key')
        header={**authenticated,'Idempotency-Key':'QA-NETWORK-AMBIGUOUS-1001'}
        first=http.post(STAFF,headers=header,json=staff_body())
        assert first.status_code==502,first.text
        with sessions() as db:
            assert db.execute(text('select count(*) from users')).scalar_one()==2
            assert db.execute(text('select count(*) from internal_staff')).scalar_one()==0
            assert db.execute(text('select count(*) from api_idempotency_requests')).scalar_one()==0
        assert len(state.records)==1
        second=http.post(STAFF,headers=header,json=staff_body())
        assert second.status_code==201,second.text
        again=http.post(STAFF,headers=header,json=staff_body())
        assert again.status_code==201 and again.json()==second.json()
        with sessions() as db:
            assert db.execute(text('select count(*) from users')).scalar_one()==3
            assert db.execute(text('select count(*) from internal_staff')).scalar_one()==1
            assert db.execute(text('select count(*) from api_idempotency_requests')).scalar_one()==1
        assert [method for method,_ in state.requests]==['POST','POST','GET','PUT'],state.requests

def test_real_http_auth_terminal_denial_fails_without_local_write(postgres_workflow,monkeypatch):
    http,sessions,engine,today,start,owner_id,hr_id,client_id,site_id,objects=postgres_workflow
    staff_db_prep(sessions)
    state=State();state.force_denial=True
    authenticated=login(http,'TEST-OWNER')
    with local_auth_server(state) as url:
        monkeypatch.setattr(settings,'SUPABASE_URL',url)
        monkeypatch.setattr(settings,'SUPABASE_SERVICE_ROLE_KEY','qa-remote-key')
        header={**authenticated,'Idempotency-Key':'QA-NETWORK-DENIAL-1001'}
        rejected=http.post(STAFF,headers=header,json=staff_body())
        assert rejected.status_code==502,rejected.text
        assert not state.records
        with sessions() as db:
            assert db.execute(text('select count(*) from internal_staff')).scalar_one()==0
            assert db.execute(text('select count(*) from api_idempotency_requests')).scalar_one()==0


def test_existing_unrelated_auth_account_never_has_password_reset(postgres_workflow,monkeypatch):
    """P0 guard: existing Auth user with same email must never be taken over."""
    http,sessions,*_ = postgres_workflow
    staff_db_prep(sessions)
    state=State()
    state.records['qa-office-0@example.in'] = {
        'id':str(uuid4()),'email':'qa-office-0@example.in',
        'app_metadata':{'destinlane_recovery_marker':'different-user-transaction'},
    }
    authenticated=login(http,'TEST-OWNER')
    with local_auth_server(state) as url:
        monkeypatch.setattr(settings,'SUPABASE_URL',url)
        monkeypatch.setattr(settings,'SUPABASE_SERVICE_ROLE_KEY','qa-remote-key')
        result=http.post(STAFF,headers={**authenticated,'Idempotency-Key':'QA-UNRELATED-AUTH-1001'},json=staff_body())
        assert result.status_code==502,result.text
        assert [method for method,_ in state.requests]==['POST','GET'],state.requests
        assert len(state.records)==1
    with sessions() as db:
        assert db.execute(text('select count(*) from internal_staff')).scalar_one()==0
        assert db.execute(text('select count(*) from api_idempotency_requests')).scalar_one()==0


def test_explicit_authorized_password_update_keeps_existing_auth_sync(monkeypatch):
    """Legacy password changes must continue working with explicit update mode."""
    from app.core.supabase_auth import provision_supabase_password_user
    state=State()
    state.records['qa-existing@example.invalid']={
        'id':str(uuid4()),'email':'qa-existing@example.invalid','app_metadata':{}
    }
    with local_auth_server(state) as url:
        monkeypatch.setattr(settings,'SUPABASE_URL',url)
        monkeypatch.setattr(settings,'SUPABASE_SERVICE_ROLE_KEY','qa-remote-key')
        response=provision_supabase_password_user(
            email='qa-existing@example.invalid',
            password='test-password-only',
            allow_existing_update=True,
        )
        assert response is not None
        assert [method for method,_ in state.requests]==['POST','GET','PUT']
