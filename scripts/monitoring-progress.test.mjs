import assert from "node:assert/strict";
import test from "node:test";
import { pollenCompleted, pollenTaskIds, snapshotCounts, tasksAwaitingDeployment } from "../apps/web/lib/monitoring-progress.ts";

const task = (id, status) => ({id, title: `Synthetic ${id}`, status});
const available = tasks => ({sha:"a".repeat(40), state:"available", reason:null, tasks});
const unavailable = {sha:null, state:"unavailable", reason:"Synthetic missing snapshot", tasks:[]};

test("only DONE earns credit; nine deferred tasks leave every required-work count", () => {
  const statuses=["PLANNED","READY","IN PROGRESS","VERIFYING","DONE","BLOCKED"];
  const required=statuses.map((status,index)=>task(`MV2-00${index+1}`,status));
  const deferred=Array.from({length:9},(_,index)=>task(`MV2-0${80+index}`,"DEFERRED"));
  const counts=snapshotCounts(available([...required,...deferred]));
  assert.equal(counts.required.length,6);
  assert.equal(counts.completed.length,1);
  assert.equal(counts.remaining.length,5);
  assert.equal(counts.inProgress,1);
  assert.equal(counts.percent,17);
  assert.ok(counts.remaining.every(value=>value.status!=="DEFERRED"));
});

test("Git and deployed revisions retain their own denominators", () => {
  const latest=available([task("MV2-001","DONE"),task("MV2-002","DONE"),task("MV2-003","PLANNED")]);
  const deployed=available([task("MV2-001","DONE"),task("MV2-002","PLANNED")]);
  assert.deepEqual([snapshotCounts(latest).percent,snapshotCounts(deployed).percent],[67,50]);
  assert.deepEqual([snapshotCounts(latest).required.length,snapshotCounts(deployed).required.length],[3,2]);
});

test("awaiting deployment compares IDs, including reopened and newly introduced tasks", () => {
  const latest=available([task("MV2-001","DONE"),task("MV2-002","BLOCKED"),task("MV2-003","DONE")]);
  const deployed=available([task("MV2-001","PLANNED"),task("MV2-002","DONE")]);
  assert.equal(snapshotCounts(latest).completed.length-snapshotCounts(deployed).completed.length,1);
  assert.deepEqual(tasksAwaitingDeployment(latest,deployed).map(value=>value.id),["MV2-001","MV2-003"]);
  assert.deepEqual(snapshotCounts(latest).remaining.map(value=>value.id),["MV2-002"]);
  assert.equal(snapshotCounts(deployed).completed[0].id,"MV2-002");
});

test("unavailable snapshots never become zero and do not erase an independently valid revision", () => {
  const deployed=available([task("MV2-001","DONE")]);
  for(const missing of [undefined,null,unavailable,{...unavailable,tasks:[task("MV2-001","DONE")]}]){
    assert.equal(snapshotCounts(missing),null);
    assert.equal(pollenCompleted(missing),null);
    assert.equal(tasksAwaitingDeployment(missing,deployed),null);
    assert.equal(tasksAwaitingDeployment(deployed,missing),null);
  }
  assert.equal(snapshotCounts(deployed).percent,100);
});

test("a valid backlog with no DONE tasks has real zero progress; zero required is not applicable", () => {
  assert.equal(snapshotCounts(available([task("MV2-073","IN PROGRESS")])).percent,0);
  assert.equal(snapshotCounts(available([task("MV2-026","DEFERRED")])).percent,null);
  assert.equal(snapshotCounts(available([])).percent,null);
});

test("100 percent is reserved for a fully completed required backlog", () => {
  const tasks=Array.from({length:1000},(_,index)=>task(`MV2-${index}`,"DONE"));
  assert.equal(snapshotCounts(available(tasks)).percent,100);
  tasks[999].status="VERIFYING";
  assert.equal(snapshotCounts(available(tasks)).percent,99);
});

test("Pollen uses only its six IDs; OPS, deferred and absent tasks give no extra credit", () => {
  const complete=available([...pollenTaskIds.map(id=>task(id,"DONE")),task("MV2-072","DONE"),task("MV2-073","DONE")]);
  assert.equal(pollenCompleted(complete),6);
  complete.tasks[0].status="DEFERRED";
  complete.tasks=complete.tasks.filter(value=>value.id!=="MV2-071");
  assert.equal(pollenCompleted(complete),4);
  assert.equal(pollenCompleted(available([task("MV2-072","DONE")])),0);
});
