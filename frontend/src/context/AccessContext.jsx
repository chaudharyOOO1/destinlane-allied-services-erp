import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useAuth } from './AuthContext';
import api from '../api/axios';

const AccessContext = createContext(null);
export const pageModules = {'/erp':'dashboard','/dashboard':'dashboard','/employees':'employees','/personnel':'recruitment','/staff':'staff','/clients':'clients','/contracts':'contracts','/sites':'sites','/rosters':'rosters','/attendance':'attendance','/billing':'billing','/payroll':'payroll','/accounts':'finance','/compliance':'compliance','/risks':'risks','/owner-executive':'owner','/users':'user_management','/ifsc-master':'employees','/company':'company'};
export function AccessProvider({children}) {
  const {user} = useAuth();
  const userId=user?.id;
  const [snapshot,setSnapshot]=useState(null);
  const [error,setError]=useState('');
  const refresh=useCallback(async()=>{
    if (!userId || user?.must_change_password) return;
    try { const {data}=await api.get(`/users/${userId}/permissions`);setSnapshot({...data,userId});setError(''); }
    catch(err){setSnapshot({userId,permissions:{},module_roles:{}});setError(err.response?.data?.detail||'Unable to load account permissions.');}
  },[userId,user?.must_change_password]);
  useEffect(()=>{refresh();},[refresh]);
  useEffect(()=>{window.addEventListener('focus',refresh);return()=>window.removeEventListener('focus',refresh);},[refresh]);
  const ready = user?.must_change_password || snapshot?.userId===userId;
  const can = key => Boolean(ready && !user?.must_change_password && snapshot?.permissions?.[key]);
  const canPage = path => {
    if (path==='/account')return true;
    const module=pageModules[path];
    return Boolean(module && can(`${module}.view`) && snapshot?.module_roles?.[module]?.includes(user?.role) && (path!=='/ifsc-master'||['OWNER','SUPER_ADMIN','ADMIN'].includes(user?.role)));
  };
  const home=Object.keys(pageModules).find(canPage)||'/account';
  return <AccessContext.Provider value={{can,canPage,home,ready,error,refresh,permissions:snapshot?.permissions||{}}}>{children}</AccessContext.Provider>;
}
export function useAccess(){return useContext(AccessContext);}
