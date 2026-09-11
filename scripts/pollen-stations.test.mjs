import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { test } from "node:test";
import { pollenStations, pollenStationSource, stationDistanceKm, orderedPollenStations, pollenChannels } from "../apps/web/lib/pollen-stations.ts";

test("all directory fields match the dated retained official source proof; no concentrations enter the directory", async () => {
  const proof = JSON.parse(await readFile(new URL('../docs/monitoring-v2/evidence/mv2-069-source-proof.json', import.meta.url), 'utf8'));
  assert.deepEqual(pollenStations, proof.forecast.points.map(p => ({ id: p.station_id, name: p.station_name, latitude: p.station_latitude, longitude: p.station_longitude })));
  assert.equal(pollenStations.length, 15);
  assert.equal(new Set(pollenStations.map(s => s.id)).size, 15);
  const metadata = proof.source_files['ogd-pollen_meta_stations.csv'];
  assert.equal(pollenStationSource.sha256, metadata.sha256);
  assert.equal(pollenStationSource.capturedAt, metadata.fetched_at);
  assert.equal(pollenStationSource.url, metadata.source_identity);
  for (const station of pollenStations) assert.deepEqual(Object.keys(station).sort(), ['id','latitude','longitude','name']);
});
test("known point distances, dateline and antipodes stay finite and symmetric", () => {
  const equator = {latitude:0, longitude:0}, degree = {latitude:0, longitude:1};
  assert.equal(stationDistanceKm(equator, equator), 0);
  assert.ok(Math.abs(stationDistanceKm(equator, degree) - 111.19508) < 0.001);
  assert.equal(stationDistanceKm(equator, degree), stationDistanceKm(degree, equator));
  assert.ok(Math.abs(stationDistanceKm({latitude:0, longitude:179.999}, {latitude:0, longitude:-179.999}) - 0.22239) < 0.001);
  assert.ok(Math.abs(stationDistanceKm(equator, {latitude:0, longitude:180}) - 20015.114) < 0.01);
});
for (const point of [{latitude:NaN,longitude:7}, {latitude:91,longitude:0}, {latitude:0,longitude:181}, {latitude:0,longitude:Infinity}]) {
  test(`invalid location is unavailable, never a fake zero (${point.latitude},${point.longitude})`, () => {
    assert.equal(stationDistanceKm(point, pollenStations[0]), null);
    assert.ok(orderedPollenStations(point, 'en-CH').every(s => s.distance === null));
  });
}
test("ranking is derived locally, has no selected-station side effect and leaves directory unchanged", () => {
  const before = JSON.stringify(pollenStations);
  const basel = pollenStations.find(s => s.id === 'PBS');
  const near = orderedPollenStations(basel, 'en-CH');
  assert.equal(near[0].id, 'PBS'); assert.equal(near[0].distance, 0);
  assert.ok(near.every((s,i) => !i || s.distance >= near[i-1].distance));
  assert.ok(orderedPollenStations(null, 'de-CH').every(s => s.distance === null));
  assert.equal(JSON.stringify(pollenStations), before);
});
for (const [allergen, observation, forecast] of [
  ['alder',true,true], ['birch',true,true], ['hazel',true,true], ['beech',true,false],
  ['ash',true,false], ['oak',true,false], ['grasses',true,true], ['ragweed',false,true], ['future',false,false],
]) test(`${allergen} keeps documented channels separate without inventing availability or samples`, () => {
  assert.deepEqual(pollenChannels(allergen), { observation, forecast });
});
