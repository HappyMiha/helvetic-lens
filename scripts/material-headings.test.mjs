import test from 'node:test';
import assert from 'node:assert/strict';
import {materialLabels} from '../apps/web/lib/material-headings.ts';

const unit = (id,path,passage='p1') => ({id,type:'passage',label:null,path,passage_ids:[passage]});
const read = (units, ids=units.map(row=>row.id), passages=['p1']) => materialLabels(ids,new Map(units.map(row=>[row.id,row])),new Set(passages));

test('article ancestry remains a saved article label, never an anonymous passage number',()=> {
  const result=read([unit('u1',['title:1','chapter:2','article:12bis','paragraph:3','passage:87'])]);
  assert.deepEqual(result.items,[[{type:'article',label:'12bis'},{type:'paragraph',label:'3'}]]);
});
test('unknown or missing hierarchy produces no invented article',()=> {
  assert.deepEqual(read([unit('u1',['passage:12'])]).items,[]);
  assert.deepEqual(read([unit('u1',['alien:12'])]).items,[]);
  assert.deepEqual(read([],['missing']).items,[]);
});
test('different document side or unrelated passage cannot supply a heading',()=> {
  assert.deepEqual(read([unit('u1',['article:12'],'other-version-passage')]).items,[]);
});
test('two sides preserve renumbering instead of silently reusing the current number',()=> {
  const old=read([unit('u1',['article:12'])]);
  const current=read([unit('u2',['article:13'])]);
  assert.equal(old.items[0][0].label,'12');
  assert.equal(current.items[0][0].label,'13');
});
test('repeated paragraph continuations deduplicate, distinct articles stay ordered and searchable',()=> {
  const result=read([unit('a',['article:1']),unit('b',['article:1','passage:2']),unit('c',['article:2']),unit('d',['article:3']),unit('e',['article:99'])]);
  assert.equal(result.items.length,3);
  assert.equal(result.additional,1);
  assert.equal(result.all.at(-1)[0].label,'99');
});
test('a chapter without articles stays a chapter rather than a guessed article',()=> {
  assert.deepEqual(read([unit('u',['title:I','chapter:2','section:3'])]).items,[[{type:'chapter',label:'2'},{type:'section',label:'3'}]]);
});
test('malformed fields and oversized labels never leak into a heading',()=> {
  for(const broken of [{id:'u',path:null,passage_ids:['p1']},{id:'u',path:['article:1'],passage_ids:null},unit('u',[null,22,'article:','article:'+ 'x'.repeat(81)])]) {
    assert.deepEqual(read([broken]).items,[]);
  }
});

test('same article number in different chapters retains its distinguishing context',()=> {
  const result=read([unit('a',['chapter:1','article:2']),unit('b',['chapter:2','article:2'])]);
  assert.deepEqual(result.items,[[{type:'chapter',label:'1'},{type:'article',label:'2'}],[{type:'chapter',label:'2'},{type:'article',label:'2'}]]);
});
