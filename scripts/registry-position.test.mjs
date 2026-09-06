import test from 'node:test';
import assert from 'node:assert/strict';
import {registryScope,saveRegistryPosition,readRegistryPosition,clearRegistryPosition} from '../apps/web/lib/registry-position.ts';
const scope=registryScope('user','org');
function store(){const values=new Map();return {values,getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)};}
const write=(storage,route='/registry?read=unread&cursor=next&locale=de-CH',target='/corpus-evidence/version?passage=p20')=>saveRegistryPosition(storage,scope,route,'row-20',target,1000);
test('preserves complete filters, page, exact row and evidence target without document content',()=>{
 const storage=store(); write(storage); const value=readRegistryPosition(storage,scope,1100);
 assert.equal(value.route,'/registry?read=unread&cursor=next&locale=de-CH'); assert.equal(value.row,'row-20'); assert.equal(value.target,'/corpus-evidence/version?passage=p20');
 assert.deepEqual(Object.keys(value).sort(),['version','scope','route','row','target','savedAt'].sort());
});
test('different user or organization cannot restore or clear another marker',()=>{
 const storage=store(); write(storage);
 for(const other of [registryScope('other','org'),registryScope('user','other'),null,'anonymous-development']) assert.equal(readRegistryPosition(storage,other,1100),null);
 clearRegistryPosition(storage,registryScope('other','org')); assert.equal(storage.values.size,1);
 assert.equal(registryScope(),null); assert.equal(registryScope(undefined,undefined,true),'anonymous-development');
});
test('expiration and future timestamps are rejected',()=>{
 const storage=store();write(storage);assert.ok(readRegistryPosition(storage,scope,1000+30*60*1000-1));
 assert.equal(readRegistryPosition(storage,scope,1000+30*60*1000),null); assert.equal(readRegistryPosition(storage,scope,999),null);
});
test('external or non-registry return routes cannot become return links',()=>{
 for(const route of ['https://evil.invalid','//evil.invalid','/\\evil.invalid','/settings','javascript:alert(1)','/registry\n']){
  const storage=store();write(storage,route);assert.equal(storage.values.size,0);
 }
 for(const target of ['https://evil.invalid','//evil.invalid','/settings','/corpus-evidence/']){
  const storage=store();write(storage,'/discover',target);assert.equal(storage.values.size,0);
 }
});
test('malformed or oversized stored records are ignored',()=>{
 for(const raw of ['{','null','[]','x'.repeat(10001)]){
  assert.equal(readRegistryPosition({getItem:()=>raw},scope,1100),null);
 }
 const storage=store();write(storage);const [key,raw]=[...storage.values][0];
 for(const patch of [{version:2},{row:''},{row:'x'.repeat(257)},{savedAt:'1000'},{target:'/outside'}]){
  storage.setItem(key,JSON.stringify({...JSON.parse(raw),...patch}));assert.equal(readRegistryPosition(storage,scope,1100),null);
 }
});
test('storage denial does not break navigation and matching marker is consumed once',()=>{
 const denied={getItem:()=>{throw Error('denied')},setItem:()=>{throw Error('denied')},removeItem:()=>{throw Error('denied')}};
 assert.doesNotThrow(()=>write(denied)); assert.equal(readRegistryPosition(denied,scope),null); assert.doesNotThrow(()=>clearRegistryPosition(denied,scope));
 const storage=store();saveRegistryPosition(storage,scope,'/registry','row','/laws/law');clearRegistryPosition(storage,scope);assert.equal(readRegistryPosition(storage,scope),null);
});
test('a later departure replaces the old marker instead of accumulating browsing history',()=>{
 const storage=store();write(storage);saveRegistryPosition(storage,scope,'/discover','second','/compare/comparison',2000);
 assert.equal(storage.values.size,1); assert.equal(readRegistryPosition(storage,scope,2001).row,'second');
});
