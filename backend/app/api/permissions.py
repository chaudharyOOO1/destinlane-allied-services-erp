from typing import Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings

MODULES = ['dashboard','employees','recruitment','staff','clients','contracts','sites','rosters','attendance','billing','payroll','finance','compliance','risks','owner','user_management','company','travel_expenses','md_accounting']
ACTIONS = ['view','create','edit','delete','approve','export','pay']
ADMINS = ['OWNER','SUPER_ADMIN','ADMIN']
OFFICE = ADMINS + ['HR','OPERATIONS','ACCOUNTS']
# Page roles reflect the backend master endpoints. Special personal attendance routes
# are separate from the attendance administration page.
MODULE_ROLES = {
 'travel_expenses':OFFICE+['SUPERVISOR'],
 'md_accounting':['OWNER','SUPER_ADMIN'],
 'dashboard':ADMINS+['ACCOUNTS'], 'employees':OFFICE, 'recruitment':ADMINS+['HR'],
 'staff':OFFICE, 'company':OFFICE, 'user_management':ADMINS,
 'clients':OFFICE+['SUPERVISOR','CLIENT'], 'contracts':OFFICE,
 'sites':ADMINS+['OPERATIONS','SUPERVISOR'], 'rosters':ADMINS+['OPERATIONS','SUPERVISOR'],
 'attendance':ADMINS+['OPERATIONS','SUPERVISOR'], 'billing':ADMINS+['ACCOUNTS'],
 'payroll':ADMINS+['HR','ACCOUNTS'], 'finance':ADMINS+['ACCOUNTS'],
 'compliance':ADMINS+['HR','ACCOUNTS'], 'risks':['OWNER','SUPER_ADMIN'], 'owner':['OWNER','SUPER_ADMIN'],
}
ROLE_MODULE_DEFAULTS = {
 'OWNER':MODULES,'SUPER_ADMIN':MODULES,'ADMIN':[m for m in MODULES if m not in {'owner','risks'}],
 'HR':['clients','employees','recruitment','attendance','compliance','company','staff'],
 'OPERATIONS':['clients','sites','rosters','attendance','company'],
 'ACCOUNTS':['dashboard','clients','contracts','billing','payroll','finance','compliance','company'],
 'SUPERVISOR':['sites','rosters','attendance'], 'CLIENT':['clients'], 'STAFF':['attendance'],
}


def permission_key(module: str, action: str = 'view') -> str:
    return f'{module}.{action}'


def permission_supported(role: str, key: str) -> bool:
    if key not in all_permission_keys(): return False
    module,action=key.split('.',1)
    if module == 'md_accounting': return role in {'OWNER','SUPER_ADMIN'} and action in {'view','create','edit','approve','export'}
    if module == 'travel_expenses':
        if role not in MODULE_ROLES[module]: return False
        if action == 'approve': return role in {'OWNER','SUPER_ADMIN','HR'}
        if action == 'pay': return role in {'OWNER','SUPER_ADMIN','ACCOUNTS'}
        return action in {'view','create','edit'}
    if module == 'payroll' and action == 'pay': return role in {'OWNER','SUPER_ADMIN','ADMIN','ACCOUNTS'}
    if action == 'pay': return False
    if module=='staff' and action in {'create','edit','approve'}: return role in {'OWNER','SUPER_ADMIN','HR'}
    if module=='attendance' and role=='STAFF': return action in {'view','create'}
    if role not in MODULE_ROLES[module]: return False
    if module in {'owner','dashboard'}: return action in {'view','export'}
    if module=='risks': return role in {'OWNER','SUPER_ADMIN'} or action in {'view','export'}
    if module=='company' and role not in ADMINS: return action=='view'
    if module in {'clients','contracts'} and role not in ADMINS: return action in {'view','export'}
    return True


def role_allows(role: str, key: str) -> bool:
    if not permission_supported(role,key): return False
    module,action=key.split('.',1)
    if module in {'travel_expenses','md_accounting'}: return True
    if role=='HR' and module=='staff': return action in {'view','create','edit'}
    if role in ADMINS: return True
    return action=='view' and module in ROLE_MODULE_DEFAULTS.get(role,[])


def _explicit_permission(db, user_id, key):
    return db.execute(text('select allowed from public.user_permissions where user_id=:user_id and permission_key=:key'),{'user_id':user_id,'key':key}).first()


def has_permission(db: Session, user, key: str) -> bool:
    role=getattr(user.role,'value',str(user.role))
    if key.startswith('md_accounting.') and user.id != settings.MD_ACCOUNTING_USER_ID: return False
    if not user.is_active or not permission_supported(role,key): return False
    if role=='OWNER' and user.is_superuser: return True
    explicit=_explicit_permission(db,user.id,key)
    return bool(explicit.allowed) if explicit is not None else role_allows(role,key)


def effective_permissions(db: Session, user, include_inactive: bool = False) -> Dict[str,bool]:
    role=getattr(user.role,'value',str(user.role))
    result={permission_key(m,a):role_allows(role,permission_key(m,a)) for m in MODULES for a in ACTIONS}
    rows=db.execute(text('select permission_key,allowed from public.user_permissions where user_id=:user_id'),{'user_id':user.id}).all()
    if not (role=='OWNER' and user.is_superuser):
        for row in rows:
            if row.permission_key in result: result[row.permission_key]=bool(row.allowed) and permission_supported(role,row.permission_key)
    if user.id != settings.MD_ACCOUNTING_USER_ID:
        for key in result:
            if key.startswith('md_accounting.'): result[key]=False
    if not user.is_active and not include_inactive: return {key:False for key in result}
    return result


def all_permission_keys() -> List[str]:
    return [permission_key(m,a) for m in MODULES for a in ACTIONS]
