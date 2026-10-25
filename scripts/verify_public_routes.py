"""Read-only public deployment smoke check, including real asset MIME types.

Usage: python scripts/verify_public_routes.py [--base-url https://erp.destinlane.in]
No login attempts, provider credentials or production writes are used.
"""
import argparse
import json
import re
import urllib.error
import urllib.parse
import urllib.request

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url',default='https://erp.destinlane.in')
args=parser.parse_args()
base=args.base_url.rstrip('/')
url=urllib.parse.urlparse(base)
if url.scheme!='https' and url.hostname not in {'127.0.0.1','localhost','::1'}:
    raise SystemExit('Use HTTPS or an isolated loopback server')
results=[]


def get(path):
    target=urllib.parse.urljoin(base+'/',path)
    if urllib.parse.urlparse(target).netloc!=url.netloc:
        raise AssertionError('Unexpected cross-origin application asset')
    with urllib.request.urlopen(target,timeout=30) as response:
        return response.read(),response.headers


for page in ['/', '/employee/login']:
    raw,headers=get(page)
    assert headers.get('X-Content-Type-Options')=='nosniff',page
    assert headers.get('X-Frame-Options')=='DENY',page
    html=raw.decode()
    scripts=re.findall(r'src="([^" ]+\.js)"',html)
    styles=re.findall(r'href="([^" ]+\.css)"',html)
    assert scripts,page+' has no script entry'
    for path in scripts+styles:
        body,asset_headers=get(path)
        expected='javascript' if path.endswith('.js') else 'text/css'
        assert expected in asset_headers.get('Content-Type',''),path+' returned a non-asset response'
        assert not body.lstrip().lower().startswith(b'<!doctype html'),path+' returned SPA HTML'
        results.append({'asset':path,'bytes':len(body),'type':asset_headers.get('Content-Type')})
    results.append({'page':page,'status':200})

for path in ['/api/v1/auth/me','/api/v1/erp/payroll/wages',
             '/api/v1/erp/payroll/staff-monthly?month=2026-10',
             '/api/v1/mobile/me/salary','/api/v1/mobile/me/documents',
             '/api/v1/erp/md-accounting/setup']:
    try:get(path)
    except urllib.error.HTTPError as error:
        assert error.code==401,(path,error.code)
        results.append({'protected':path,'anonymous_status':401})
    else:raise AssertionError('Anonymous access unexpectedly succeeded: '+path)
print(json.dumps({'result':'PASS','checks':results},indent=2))
