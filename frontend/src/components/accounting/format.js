export const money=value=>new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR'}).format(Number(value||0));
export function accountingError(error){const detail=error?.response?.data?.detail;return Array.isArray(detail)?detail.map(item=>item.msg).join(' '):typeof detail==='string'?detail:'Could not confirm this action. Check your existing records before retrying.';}
