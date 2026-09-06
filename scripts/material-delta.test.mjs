import test from 'node:test';
import assert from 'node:assert/strict';
import {materialDelta} from '../apps/web/lib/material-delta.ts';
const part=(kind,text)=>({kind,text});
const read=(before,after)=>materialDelta({old:{text:before.map(x=>x.text).join('')},new:{text:after.map(x=>x.text).join('')},old_parts:before,new_parts:after});
const plain=parts=>parts.map(x=>x.text).join('');
const marked=(parts,kind)=>parts.filter(x=>x.kind===kind).map(x=>x.text).join('');

test('late changed deadline is visible after a long unchanged introduction',()=>{
 const prefix='Unchanged introduction. '.repeat(100)+'Deadline: ';
 const value=read([part('equal',prefix),part('removed','10'),part('equal',' days.')],[part('equal',prefix),part('added','30'),part('equal',' days.')]);
 assert.equal(value.focused,true); assert.equal(value.fragments,1); assert.equal(value.limited,true);
 assert.equal(marked(value.old,'removed'),'10'); assert.equal(marked(value.new,'added'),'30');
 assert.match(plain(value.old),/Deadline: 10 days\.$/); assert.match(plain(value.new),/Deadline: 30 days\.$/);
});
test('insertion and deletion preserve matching context without inventing a missing passage',()=>{
 const before=[part('equal','Records '),part('equal','required.')];
 const after=[part('equal','Records '),part('added','are now '),part('equal','required.')];
 const insertion=read(before,after);
 assert.equal(plain(insertion.old),'Records required.'); assert.equal(marked(insertion.new,'added'),'are now ');
 assert.equal(insertion.limited,false);
 const deletion=read(after.map(p=>({...p,kind:p.kind==='added'?'removed':p.kind})),before);
 assert.equal(marked(deletion.old,'removed'),'are now '); assert.equal(plain(deletion.new),'Records required.');
});
test('entirely added or removed passage has a genuinely empty counterpart',()=>{
 assert.deepEqual(read([], [part('added','New duty')]).old,[]);
 assert.equal(marked(read([part('removed','Old duty')],[]).old,'removed'),'Old duty');
 assert.deepEqual(read([part('removed','Old duty')],[]).new,[]);
});
test('additional fragments remain counted and omission is explicit',()=>{
 const value=read([part('removed','10'),part('equal',' days; '),part('removed','old duty')],[part('added','30'),part('equal',' days; '),part('added','new duty')]);
 assert.equal(value.fragments,2); assert.equal(value.limited,true);
 assert.equal(plain(value.old),'10 days; …'); assert.equal(plain(value.new),'30 days; …');
});
test('mismatched saved text or alignment never receives invented word highlighting',()=>{
 const invalids=[
 {old:{text:'real old'},new:{text:'real new'},old_parts:[part('removed','wrong')],new_parts:[part('added','real new')]},
 {old:{text:'A'},new:{text:'B'},old_parts:[part('equal','A')],new_parts:[part('equal','B')]},
 {old:{text:'A'},new:{text:'B'},old_parts:[part('added','A')],new_parts:[part('added','B')]},
 {old:{text:'A'},new:{text:'B'},old_parts:null,new_parts:[null]},
 ];
 for(const input of invalids){const value=materialDelta(input); assert.equal(value.focused,false); assert.equal(marked(value.old,'removed'),''); assert.equal(marked(value.new,'added'),'');}
});
test('unchanged or absent evidence does not assert a change',()=>{
 assert.equal(read([part('equal','same')],[part('equal','same')]).focused,false);
 assert.equal(materialDelta().focused,false);
});
test('bounded previews preserve Unicode code points and signal every truncation',()=>{
 const value=read([part('equal','🦆'.repeat(500)),part('removed','é'.repeat(500)),part('equal','🌍'.repeat(500))],[part('equal','🦆'.repeat(500)),part('added','ö'.repeat(500)),part('equal','🌍'.repeat(500))]);
 for(const side of [value.old,value.new]){
  assert.equal(Array.from(plain(side)).length,251); assert.equal(plain(side).isWellFormed(),true);
  assert.equal(side.filter(p=>p.kind==='omission').length,3);
 }
 assert.equal(value.limited,true);
});
test('fallback is bounded without changing persisted input',()=>{
 const input={old:{text:'A'.repeat(500)},new:{text:'B'.repeat(500)}};
 const snapshot=structuredClone(input); const value=materialDelta(input);
 assert.equal(plain(value.old).length,248); assert.equal(value.limited,true); assert.deepEqual(input,snapshot);
});
