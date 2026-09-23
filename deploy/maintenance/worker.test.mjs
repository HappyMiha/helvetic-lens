import test from 'node:test';
import assert from 'node:assert/strict';
import {createHandler, MAINTENANCE_ORIGIN, PREVIEW_PATH} from './worker.mjs';
const page = '<!doctype html><h1 id="maintenance-title">Back on 24 September 2026 at 08:00 CEST</h1>';
const navigation = (path='/private?query=private', method='GET') => new Request('https://helveticlens.ch'+path, {method, headers:{Accept:'text/html',Cookie:'private-session',Authorization:'Bearer private-token'}});

test('healthy and authentication responses pass through without a public asset request', async()=>{
 for(const status of [200,302,401,403,404]) {
  const expected = new Response('private application body',{status,headers:{'Set-Cookie':'private-cookie','Cache-Control':'private'}});
  const input = navigation();
  const app=createHandler(async request=>{assert.equal(request,input);return expected;});
  const actual=await app.fetch(input);
  assert.equal(actual,expected);assert.equal(actual.headers.get('Set-Cookie'),'private-cookie');
 }
});

test('origin failures become an uncached HTML notice without forwarding private data', async()=>{
 for(const status of [500,502,503,504,520,521,522,523,524,525,526,530,null]) {
  const calls=[];
  const app=createHandler(async(request,options)=>{
   calls.push([request,options]);
   if(request instanceof Request) {if(status===null)throw new Error('offline');return new Response('origin error',{status});}
   assert.equal(request,MAINTENANCE_ORIGIN+'/maintenance.html');
   assert.deepEqual(options.headers,{Accept:'text/html'});
   return new Response(page,{headers:{'Content-Type':'text/html','Set-Cookie':'must-not-leak'}});
  });
  const result=await app.fetch(navigation());
  assert.equal(result.status,503);assert.equal(await result.text(),page);
  assert.equal(result.headers.get('cache-control'),'no-store, max-age=0');
  assert.ok(result.headers.get('retry-after'));assert.equal(result.headers.get('set-cookie'),null);
  assert.equal(result.headers.get('x-helvetic-maintenance'),'edge');assert.equal(calls.length,2);
 }
});

test('API and non-navigation failures preserve their original responses',async()=>{
 for(const input of [navigation('/api/ready'),new Request('https://helveticlens.ch/assets/script.js',{headers:{Accept:'*/*'}}),navigation('/api/action','POST')]) {
  const expected = new Response('{"error":"original"}',{status:502});let calls=0;
  const app=createHandler(async()=>{calls++;return expected;});
  assert.equal(await app.fetch(input),expected);assert.equal(calls,1);
 }
});

test('a disconnected mutation is never repeated or sent to the asset host',async()=>{
 let calls=0;const app=createHandler(async()=>{calls++;throw new Error('offline');});
 const result=await app.fetch(navigation('/api/action','POST'));
 assert.equal(result.status,503);assert.equal((await result.json()).error,'maintenance');assert.equal(calls,1);
});

test('preview and HEAD work without the origin, and asset failure has a local notice',async()=>{
 let calls=0;const app=createHandler(async url=>{calls++;assert.equal(url,MAINTENANCE_ORIGIN+'/maintenance.html');throw new Error('asset host offline');});
 const preview=await app.fetch(navigation(PREVIEW_PATH));assert.equal(preview.status,503);assert.match(await preview.text(),/08:00 CEST/);
 const head=await app.fetch(navigation(PREVIEW_PATH,'HEAD'));assert.equal(head.status,503);assert.equal(await head.text(),'');assert.equal(calls,2);
});

test('the next navigation recovers immediately without retaining a cached outage',async()=>{
 let healthy=false;const app=createHandler(async request=>request instanceof Request ? new Response(healthy?'application':'offline',{status:healthy?200:530}):new Response(page,{headers:{'Content-Type':'text/html'}}));
 assert.equal((await app.fetch(navigation())).status,503);healthy=true;
 const next=await app.fetch(navigation());assert.equal(next.status,200);assert.equal(await next.text(),'application');
});
