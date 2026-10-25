"""Verify both migration formats on disposable PostgreSQL 17 databases."""
import os
import shutil
import subprocess
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url
from test_postgres_workflow import postgres_workflow

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/'supabase/migrations/20261022190000_api_idempotency.sql'

def test_supabase_migration_fresh_apply_and_safe_reapply(postgres_workflow):
    http, sessions, engine, *_ = postgres_workflow
    admin_url=make_url(os.environ['TEST_POSTGRES_ADMIN_URL'])
    host=admin_url.host or admin_url.query.get('host') or '/var/run/postgresql'
    port=str(admin_url.port or admin_url.query.get('port') or 5432)
    user=admin_url.username or os.environ.get('USER','postgres')
    env=os.environ.copy()
    if admin_url.password:
        env['PGPASSWORD']=admin_url.password
    with sessions() as db:
        db.execute(text('drop table public.api_idempotency_requests'))
        db.commit()
    args=[shutil.which('psql'),'-v','ON_ERROR_STOP=1','-h',host,'-p',port,'-U',user,
          '-d',engine.url.database,'-f',str(SQL)]
    for index in range(2):
        run=subprocess.run(args,env=env,capture_output=True,text=True,timeout=30)
        assert run.returncode==0,(index,run.stderr[-1200:],run.stdout[-350:])
    with engine.connect() as db:
        assert db.execute(text("select to_regclass('public.api_idempotency_requests') is not null")).scalar_one()
        assert db.execute(text("select relrowsecurity from pg_class where oid='public.api_idempotency_requests'::regclass")).scalar_one()
        columns=db.execute(text("""select column_name from information_schema.columns where table_schema='public'
          and table_name='api_idempotency_requests'""")).scalars().all()
        assert set(columns)=={'id','actor_id','operation','request_key','request_digest','response','created_at'}
        unique=db.execute(text("""select count(*) from pg_constraint
          where conrelid='public.api_idempotency_requests'::regclass and contype='u'
          and conname='uq_api_idempotency_actor_operation_key'""")).scalar_one()
        assert unique==1
        for role in ('anon','authenticated'):
            assert not db.execute(text("select has_table_privilege(:role,'public.api_idempotency_requests','SELECT')"),{'role':role}).scalar_one()
        assert db.execute(text("select count(*) from users")).scalar_one()>=2
