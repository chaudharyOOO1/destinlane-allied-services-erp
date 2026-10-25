"""Local generated-data restore drill. This never certifies production backups.

Set TEST_POSTGRES_ADMIN_URL (loopback only) and optionally PG_BIN_DIR.
Two uniquely named disposable databases are created and removed.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
url = make_url(os.environ['TEST_POSTGRES_ADMIN_URL'])
if url.host not in {'127.0.0.1', 'localhost', '::1'}:
    raise SystemExit('Use isolated loopback PostgreSQL only.')
admin = create_engine(url, isolation_level='AUTOCOMMIT')
names = ['erp_restore_' + uuid4().hex for _ in range(2)]
created = []
env = {**os.environ, 'PGHOST':url.host, 'PGPORT':str(url.port or 5432), 'PGUSER':url.username or ''}
if url.password: env['PGPASSWORD'] = url.password


def run(args, **kwargs):
    result = subprocess.run(args, env=kwargs.pop('env',env), capture_output=True, text=True, timeout=60, **kwargs)
    if result.returncode: raise RuntimeError('Command failed: ' + Path(args[0]).name)


def fingerprint(engine):
    with engine.connect() as conn:
        tables = conn.execute(text("select tablename,rowsecurity from pg_tables where schemaname='public' order by tablename")).all()
        counts = {name:conn.execute(text(f'select count(*) from public."{name}"')).scalar_one() for name,_ in tables}
        name = conn.execute(text("select profile->>'legal_name' from company_settings where id=1")).scalar_one()
        return {'tables':[list(row) for row in tables], 'counts':counts, 'fixture':name}


try:
    with admin.connect() as conn:
        for name in names:
            conn.exec_driver_sql(f'create database "{name}"')
            created.append(name)
    source_url = url.set(database=names[0])
    run([sys.executable,'-m','alembic','upgrade','head'],cwd=root/'backend',env={**env,'DATABASE_URL':source_url.render_as_string(hide_password=False)})
    original = create_engine(source_url)
    with original.begin() as conn:
        conn.execute(text("update company_settings set profile=jsonb_build_object('legal_name','Generated local restore proof') where id=1"))
    expected = fingerprint(original)
    original.dispose()
    bin_dir = Path(os.environ.get('PG_BIN_DIR',''))
    with tempfile.TemporaryDirectory(prefix='das-restore-') as directory:
        dump = str(Path(directory)/'test-data.dump')
        run([str(bin_dir/'pg_dump'),'--format=custom','--file',dump,'--dbname',names[0]])
        run([str(bin_dir/'pg_restore'),'--exit-on-error','--no-owner','--dbname',names[1],dump])
        recovered = create_engine(url.set(database=names[1]))
        actual = fingerprint(recovered)
        recovered.dispose()
        assert actual == expected, 'Restored counts, RLS metadata or generated fixture differ'
    print(json.dumps({'result':'PASS','tables':len(expected['tables']), 'scope':'Generated local data; production offsite recovery remains unverified'}))
finally:
    with admin.connect() as conn:
        for name in reversed(created): conn.exec_driver_sql(f'drop database if exists "{name}" with (force)')
    admin.dispose()
