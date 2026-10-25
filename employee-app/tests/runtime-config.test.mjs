import {test} from 'node:test';
import assert from 'node:assert/strict';
import {employeeRuntime} from '../src/lib/runtimeConfig.js';
test('web requests stay on the ERP origin and retain the employee prefix',()=>{
 assert.deepEqual(employeeRuntime(false),{apiBase:'/api/v1',routerBase:'/employee'});
});
test('installed apps use HTTPS ERP independently of their local asset origin',()=>{
 assert.deepEqual(employeeRuntime(true),{apiBase:'https://erp.destinlane.in/api/v1',routerBase:'/'});
 assert.equal(employeeRuntime(true,'https://erp.example.test/api/v1/').apiBase,'https://erp.example.test/api/v1');
});
test('native configuration rejects insecure or credential-bearing endpoints',()=>{
 for(const value of ['http://erp.example.test','/api/v1','https://user:secret@erp.example.test','https://erp.example.test?token=x']){
  assert.throws(()=>employeeRuntime(true,value));
 }
});
