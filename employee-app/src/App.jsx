import { Toaster } from '@/components/ui/toaster';
import { BrowserRouter, HashRouter, Route, Routes } from 'react-router-dom';
import { Capacitor } from '@capacitor/core';
import { employeeRuntime } from '@/lib/runtimeConfig';
import PageNotFound from './lib/PageNotFound';
import ScrollToTop from './components/ScrollToTop';
import PhoneSessionGuard from '@/components/PhoneSessionGuard';
import Dashboard from '@/pages/Dashboard';
import PhoneLogin from '@/pages/PhoneLogin';

export default function App() {
  const native = Capacitor.isNativePlatform();
  const Router = native ? HashRouter : BrowserRouter;
  return <Router basename={employeeRuntime(native).routerBase}><ScrollToTop/><Routes>
    <Route path="/login" element={<PhoneLogin/>}/>
    <Route element={<PhoneSessionGuard/>}><Route path="/" element={<Dashboard/>}/></Route>
    <Route path="*" element={<PageNotFound/>}/>
  </Routes><Toaster/></Router>;
}
