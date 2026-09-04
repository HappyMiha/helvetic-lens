import assert from "node:assert/strict";
import test from "node:test";
import { MarvinVoice, RemarkDelivery } from "../apps/web/lib/marvin-delivery.ts";

test("arrival, clicks, scroll and remounts share a route budget", () => {
  const entries = new Map();
  const storage = { getItem: k => entries.get(k), setItem: (k,v) => entries.set(k,v) };
  const first = new RemarkDelivery(storage);
  assert.equal(first.reserve("/logs", 0), true);
  assert.equal(first.reserve("/logs", 1000), false);
  const remount = new RemarkDelivery(storage);
  assert.equal(remount.reserve("/logs", 120_000), false);
  assert.equal(remount.reserve("/sources", 1000), false);
  assert.equal(remount.reserve("/logs", 900_000), true);
});

test("model repetition rotates to unused context and stops when exhausted", () => {
  const delivery = new RemarkDelivery();
  assert.equal(delivery.choose(["context", "progress"], 0), "context");
  assert.equal(delivery.choose(["context", "progress"], 900_000), "progress");
  assert.equal(delivery.choose(["context", "progress"], 1_800_000), null);
  assert.equal(delivery.choose(["context"], 86_400_000), "context");
});

test("denied storage still bounds reminders", () => {
  const delivery = new RemarkDelivery({ getItem() { throw Error(); }, setItem() { throw Error(); } });
  assert.equal(delivery.reserve("/logs", 0), true);
  assert.equal(delivery.reserve("/logs", 100), false);
});

function voiceHarness() {
  const states = [];
  const synth = new EventTarget();
  synth.voices = [];
  synth.spoken = [];
  synth.getVoices = () => synth.voices;
  synth.resume = () => {};
  synth.cancel = () => {};
  synth.speak = utterance => synth.spoken.push(utterance);
  class Utterance { constructor(text) { this.text = text; } }
  const voice = new MarvinVoice(synth, Utterance, state => states.push(state));
  return { synth, states, voice };
}

test("speech waits for asynchronously loaded voices and uses the available voice language", t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { synth, states, voice } = voiceHarness();
  voice.speak("Hello", "en-CH");
  assert.equal(synth.spoken.length, 0);
  synth.voices = [{ lang: "en-US", localService: true }];
  synth.dispatchEvent(new Event("voiceschanged"));
  assert.equal(synth.spoken.length, 1);
  assert.equal(synth.spoken[0].lang, "en-US");
  synth.spoken[0].onstart();
  t.mock.timers.tick(6000);
  assert.equal(states.at(-1), "speaking");
  synth.spoken[0].onend();
  assert.equal(states.at(-1), "idle");
  voice.stop();
});

test("silent browser rejection is surfaced and explicit retry can recover", t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { synth, states, voice } = voiceHarness();
  synth.voices = [{ lang: "de-DE", localService: true }];
  voice.speak("Hallo", "de-CH");
  t.mock.timers.tick(5001);
  assert.equal(states.at(-1), "blocked");
  voice.speak("Hallo", "de-CH");
  synth.spoken[0].onend(); // stale cancelled callback must not clear the new state
  assert.equal(states.at(-1), "loading");
  synth.spoken[1].onstart();
  assert.equal(states.at(-1), "speaking");
  voice.stop();
});

test("missing voices and explicit synthesis errors are visible", t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { synth, states, voice } = voiceHarness();
  voice.speak("Hello", "en-CH");
  t.mock.timers.tick(1501);
  assert.equal(states.at(-1), "unavailable");
  synth.voices = [{ lang: "en-US", localService: true }];
  voice.speak("Hello", "en-CH");
  synth.spoken[0].onerror({ error: "not-allowed" });
  assert.equal(states.at(-1), "blocked");
  voice.stop();
});
