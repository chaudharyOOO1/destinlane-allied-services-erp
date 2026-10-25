import { Toaster } from '@/components/ui/toaster';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import PageNotFound from './lib/PageNotFound';
import ScrollToTop from './components/ScrollToTop';
import PhoneSessionGuard from '@/components/PhoneSessionGuard';
import Dashboard from '@/pages/Dashboard';
import PhoneLogin from '@/pages/PhoneLogin';

export default function App() {
  return <Router basename="/employee"><ScrollToTop/><Routes>
    <Route path="/login" element={<PhoneLogin/>}/>
    <Route element={<PhoneSessionGuard/>}><Route path="/" element={<Dashboard/>}/></Route>
    <Route path="*" element={<PageNotFound/>}/>
  </Routes><Toaster/></Router>;
}
