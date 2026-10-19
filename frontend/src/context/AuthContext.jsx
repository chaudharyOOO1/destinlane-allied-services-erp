import {createContext, useCallback, useContext, useEffect, useMemo, useRef, useState} from 'react';
import api from '../api/axios';

const AuthContext=createContext(null);
const TOKEN_KEY='destinlane_access_token';

export function AuthProvider({children}){
  const [user,setUser]=useState(null),[loading,setLoading]=useState(true),[authError,setAuthError]=useState('');
  const authVersion=useRef(0);
  const refreshUser=useCallback(async()=>{
    const current=++authVersion.current;
    const token=localStorage.getItem(TOKEN_KEY);
    if(!token){setUser(null);setLoading(false);setAuthError('');return null;}
    setLoading(true);setAuthError('');
    try{
      const {data}=await api.get('/auth/me');
      if(current!==authVersion.current||localStorage.getItem(TOKEN_KEY)!==token)return null;
      setUser(data);return data;
    }catch(error){
      if(current!==authVersion.current||localStorage.getItem(TOKEN_KEY)!==token)return null;
      setUser(null);
      if(error.response?.status===401){localStorage.removeItem(TOKEN_KEY);}
      else setAuthError('Your account could not be checked. Check your connection and retry.');
      return null;
    }finally{if(current===authVersion.current)setLoading(false);}
  },[]);
  useEffect(()=>{refreshUser();},[refreshUser]);
  const login=useCallback(async(loginId,password)=>{
    const current=++authVersion.current;
    try{
      const {data}=await api.post('/auth/login',{login_id:loginId.trim(),password});
      if(current!==authVersion.current)return null;
      localStorage.setItem(TOKEN_KEY,data.access_token);setAuthError('');setUser(data.user);return data.user;
    }finally{if(current===authVersion.current)setLoading(false);}
  },[]);
  const logout=useCallback(()=>{authVersion.current++;setLoading(false);localStorage.removeItem(TOKEN_KEY);setAuthError('');setUser(null);window.location.assign('/login');},[]);
  const value=useMemo(()=>({user,loading,authError,login,logout,refreshUser}),[user,loading,authError,login,logout,refreshUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth(){const value=useContext(AuthContext);if(!value)throw new Error('useAuth must be used inside AuthProvider');return value;}
export {TOKEN_KEY};
