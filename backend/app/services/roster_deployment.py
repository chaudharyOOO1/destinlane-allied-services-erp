import json
from datetime import date,timedelta
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel,ConfigDict,Field,model_validator
from sqlalchemy import text
from app.core.business_time import business_date

class Assignment(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    site_id:int=Field(gt=0)
    guard_id:int=Field(gt=0)
    date:date
    shift_type:Literal['DAY','NIGHT','GENERAL']
    notes:str=Field(default='',max_length=2000)

class Update(Assignment):
    version:int=Field(gt=0)
    reason:str=Field(min_length=3,max_length=1000)

class Cancel(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    version:int=Field(gt=0)
    reason:str=Field(min_length=3,max_length=1000)

class Repeat(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    site_id:int=Field(gt=0)
    guard_id:int=Field(gt=0)
    start:date
    end:date
    shift_type:Literal['DAY','NIGHT','GENERAL']
    weekdays:list[int]=Field(default_factory=lambda:list(range(7)),min_length=1,max_length=7)
    notes:str=Field(default='',max_length=2000)
    @model_validator(mode='after')
    def valid(self):
        if self.end<self.start or (self.end-self.start).days>30: raise ValueError('Repeat schedules cover up to 31 days.')
        if len(set(self.weekdays))!=len(self.weekdays) or any(x not in range(7) for x in self.weekdays): raise ValueError('Choose unique weekdays from Monday (0) to Sunday (6).')
        if not self.dates(): raise ValueError('No selected weekdays fall in this range.')
        return self
    def dates(self):return [self.start+timedelta(days=n) for n in range((self.end-self.start).days+1) if (self.start+timedelta(days=n)).weekday() in self.weekdays]


def row(db,sql,params=None):return db.execute(text(sql),params or {}).mappings().first()


def deployable(db,guard_id,target=None,lock=False):
    target=target or business_date()
    person=row(db,"""select g.id,g.employee_id,cast(g.status as text) as guard_status,e.name,e.employee_code,e.status,e.client_id,e.branch,e.category,e.profile from guard_profiles g join employees e on e.id=g.employee_id where g.id=:id"""+(' for update of g,e' if lock else ''),{'id':guard_id})
    if not person: raise HTTPException(404,'Employee deployment profile not found.')
    if person['guard_status']!='ACTIVE' or person['status'].upper()!='ACTIVE': raise HTTPException(409,'Employee must be active before deployment.')
    if not row(db,"select employee_id from employee_joining_drafts where employee_id=:id and status='APPROVED'",{'id':str(person['employee_id'])}): raise HTTPException(409,'Employee joining approval is incomplete.')
    needed={'POLICE_VERIFICATION','MEDICAL_FITNESS'}|({'GUN_LICENSE'} if person['category']=='GUNMAN' else set())
    documents=db.execute(text("select document_type from employee_documents where employee_id=:id and verification_status='VERIFIED' and storage_path is not null and sha256 is not null and expiry_date>=:target and (issue_date is null or issue_date<=:target)"),{'id':str(person['employee_id']),'target':target}).mappings().all()
    missing=needed-{d['document_type'] for d in documents}
    if missing: raise HTTPException(409,'Compliance missing or expired on '+str(target)+': '+', '.join(sorted(missing)))
    return dict(person)


def site_for(db,site_id,person,target,lock=False):
    site=row(db,'select s.*,c.is_active as client_active from sites s join clients c on c.id=s.client_id where s.id=:id'+(' for update of s,c' if lock else ''),{'id':site_id})
    if not site or not site['is_active'] or not site['client_active']: raise HTTPException(409,'Choose an active site belonging to an active client.')
    if site['client_id']!=person['client_id'] or (site['branch'] and site['branch']!=person['branch']): raise HTTPException(409,'Employee client and branch must match the deployment site.')
    if site.get('contract_id'):
        contract=row(db,'select * from client_contracts where id=:id'+(' for update' if lock else ''),{'id':site['contract_id']})
        if not contract or contract['status'] not in {'ACTIVE','RENEWED'} or not contract['contract_start_date']<=target<=contract['contract_end_date']: raise HTTPException(409,'The linked site contract must be active and cover the deployment date.')
        vertical=(person.get('profile') or {}).get('vertical')
        allowed=(contract.get('profile') or {}).get('service_verticals',[])
        if allowed and ('HEALTHCARE' if vertical=='NURSING' else vertical) not in allowed: raise HTTPException(409,'Employee service vertical is outside the linked contract scope.')
    return site


def conflict(db,guard_id,target,exclude=0):
    existing=row(db,"select id from shift_rosters where guard_id=:guard and date=:date and status in ('SCHEDULED','COMPLETED') and id<>:exclude",{'guard':guard_id,'date':target,'exclude':exclude})
    if existing: raise HTTPException(409,'Employee already has an active assignment on '+str(target)+'. Cancel or change that assignment first.')


def validate_assignment(db,data,exclude=0):
    if data.date<business_date(): raise HTTPException(422,'New or changed deployments cannot be scheduled in the past.')
    person=deployable(db,data.guard_id,data.date,True)
    site_for(db,data.site_id,person,data.date,True)
    conflict(db,data.guard_id,data.date,exclude)


def audit(db,record,user,action,reason='',before=None):
    db.execute(text('insert into roster_history(roster_id,changed_by,action,version,details) values (:id,:user,:action,:version,cast(:detail as jsonb))'),{'id':record['id'],'user':user.id,'action':action,'version':record['version'],'detail':json.dumps({'reason':reason,'before':dict(before) if before else None,'after':dict(record)},default=str)})


def insert(db,data,user):
    record=dict(db.execute(text("insert into shift_rosters(site_id,guard_id,date,shift_type,status,notes,created_by,updated_by) values (:site_id,:guard_id,:date,:shift_type,'SCHEDULED',:notes,:user,:user) returning *"),{**data.model_dump(),'user':user.id}).mappings().one())
    audit(db,record,user,'SCHEDULE');return record


def editable(db,rid,version):
    record=row(db,'select * from shift_rosters where id=:id for update',{'id':rid})
    if not record: raise HTTPException(404,'Assignment not found.')
    if record['version']!=version: raise HTTPException(409,'Assignment changed. Refresh before editing.')
    if record['status']!='SCHEDULED': raise HTTPException(409,'Only scheduled assignments can be changed or cancelled.')
    if row(db,'select id from attendance where roster_id=:id',{'id':rid}): raise HTTPException(409,'Attendance has been recorded. This assignment is locked.')
    return dict(record)
