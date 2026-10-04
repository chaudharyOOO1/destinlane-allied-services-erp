import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

export function apiError(error, fallback='Unable to save. Please retry.') {
  const detail=error.response?.data?.detail;
  return Array.isArray(detail)?detail.map(x=>`${x.loc?.slice(-1)[0]||'Field'}: ${x.msg}`).join(' · '):typeof detail==='string'?detail:fallback;
}
export const inputClass='mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 disabled:bg-slate-50';
export const buttonClass='rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50';
export function MasterField({label,value,onChange,type='text',options,required=false,disabled=false,...props}) {
  const id=label.toLowerCase().replaceAll(' ','-');
  return <label className="block text-xs font-medium text-slate-600" htmlFor={id}>{label}{required?' *':''}
    {options?<select id={id} className={inputClass} value={value??''} onChange={e=>onChange(e.target.value)} required={required} disabled={disabled}>{options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</select>:type==='textarea'?<textarea id={id} className={inputClass} value={value??''} onChange={e=>onChange(e.target.value)} required={required} disabled={disabled} rows={3} {...props}/>:<input id={id} className={inputClass} type={type} value={value??''} onChange={e=>onChange(e.target.value)} required={required} disabled={disabled} {...props}/>}
  </label>;
}
export function MasterDialog({title,subtitle,error,saving,editable,onClose,onSubmit,children,footer,wide=true}) {
  const ref=useRef(null);
  const closeRef=useRef(onClose);
  useEffect(()=>{closeRef.current=onClose;},[onClose]);
  useEffect(()=>{
    const previous=document.activeElement;
    const panel=ref.current;
    const controls=()=>Array.from(panel.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]'));
    controls()[0]?.focus();
    const oldOverflow=document.body.style.overflow;document.body.style.overflow='hidden';
    const handle=e=>{
      if(e.key==='Escape'){e.preventDefault();closeRef.current();}
      if(e.key==='Tab'){
        const list=controls(),first=list[0],last=list.at(-1);
        if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}
        else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
      }
    };
    panel.addEventListener('keydown',handle);
    return()=>{panel.removeEventListener('keydown',handle);document.body.style.overflow=oldOverflow;previous?.focus();};
  },[]);
  return <div className="fixed inset-0 z-[60] overflow-y-auto bg-slate-950/40 p-3 sm:p-7"><form ref={ref} onSubmit={onSubmit} role="dialog" aria-modal="true" aria-labelledby="master-title" className={`mx-auto ${wide?'max-w-4xl':'max-w-2xl'} space-y-5 rounded-2xl bg-white p-5 sm:p-7`}>
    <div className="flex items-start justify-between gap-4"><div><h2 id="master-title" className="text-xl font-semibold">{title}</h2>{subtitle&&<p className="mt-1 text-sm text-slate-500">{subtitle}</p>}</div><button type="button" className={buttonClass} aria-label="Close profile" onClick={onClose} disabled={saving}><X size={18}/></button></div>
    {error&&<p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
    <fieldset disabled={!editable||saving} className="space-y-5 disabled:opacity-80">{children}</fieldset>
    <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4"><div className="text-xs text-slate-500">{footer}</div>{editable&&<button disabled={saving} className="rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white">{saving?'Saving…':'Save record'}</button>}</div>
  </form></div>;
}
export function HistoryList({rows}) {
  return <div className="max-h-48 overflow-y-auto rounded-lg border"><table className="w-full text-left text-xs"><thead className="bg-slate-50"><tr>{['Action','Version','Changed','Account'].map(x=><th key={x} className="p-2">{x}</th>)}</tr></thead><tbody>{rows.map(h=><tr key={h.id} className="border-t"><td className="p-2">{h.action.replaceAll('_',' ')}</td><td className="p-2">{h.snapshot?.version??'—'}</td><td className="p-2">{new Date(h.created_at).toLocaleString('en-IN')}</td><td className="p-2">{h.changed_by?`#${h.changed_by}`:'—'}</td></tr>)}</tbody></table>{!rows.length&&<p className="p-3 text-sm text-slate-500">No revisions yet.</p>}</div>;
}
