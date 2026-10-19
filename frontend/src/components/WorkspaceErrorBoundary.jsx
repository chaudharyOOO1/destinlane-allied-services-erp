import {Component} from 'react';

/** Keep an unexpected rendering failure recoverable without discarding saved records. */
export default class WorkspaceErrorBoundary extends Component {
  state={failed:false};
  static getDerivedStateFromError(){return {failed:true};}
  render(){
    if(this.state.failed)return <div className="flex min-h-screen items-center justify-center bg-slate-50 px-5"><main className="w-full max-w-lg rounded-xl border border-slate-200 bg-white p-7"><h1 className="text-xl font-semibold text-slate-900">This workspace could not open</h1><p role="alert" className="mt-3 text-sm leading-6 text-slate-600">Reload to try again. If you were saving a record, check whether it was saved before submitting it again.</p><button onClick={()=>window.location.reload()} className="mt-5 rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-medium text-white">Reload workspace</button></main></div>;
    return this.props.children;
  }
}
