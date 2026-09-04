const COOLDOWN = 15 * 60 * 1000;
const GLOBAL_COOLDOWN = 2 * 60 * 1000;
const REPEAT_WINDOW = 24 * 60 * 60 * 1000;
const KEY = "helvetic_lens_marvin_delivery_v2";

type Memory = { routes: Record<string, number>; remarks: Record<string, number>; last?: number };

/** One budget shared by arrival, activity, scroll and completion notifications. */
export class RemarkDelivery {
  private memory: Memory = { routes: {}, remarks: {} };
  private storage?: Pick<Storage, "getItem" | "setItem">;
  constructor(storage?: Pick<Storage, "getItem" | "setItem">) {
    this.storage = storage;
    try {
      const saved = JSON.parse(storage?.getItem(KEY) || "null");
      if (saved && typeof saved.routes === "object" && saved.routes && typeof saved.remarks === "object" && saved.remarks)
        this.memory = saved;
    } catch { /* In-memory limits still apply when storage is unavailable. */ }
  }
  reserve(route: string, now = Date.now()): boolean {
    if (now - (this.memory.routes[route] ?? -Infinity) < COOLDOWN ||
        now - (this.memory.last ?? -Infinity) < GLOBAL_COOLDOWN) return false;
    // Reserve before awaiting the model, so simultaneous triggers cannot race.
    this.memory.routes[route] = now;
    this.memory.last = now;
    this.save(now);
    return true;
  }
  choose(candidates: string[], now = Date.now()): string | null {
    const key = candidates.find((candidate) =>
      now - (this.memory.remarks[candidate] ?? -Infinity) >= REPEAT_WINDOW);
    if (!key) return null;
    this.memory.remarks[key] = now;
    this.save(now);
    return key;
  }
  private save(now: number) {
    for (const entries of [this.memory.routes, this.memory.remarks]) {
      for (const [key, time] of Object.entries(entries)) {
        if (!Number.isFinite(time) || now - time >= REPEAT_WINDOW) delete entries[key];
      }
    }
    try { this.storage?.setItem(KEY, JSON.stringify(this.memory)); } catch { /* Use memory. */ }
  }
}

export type VoiceState = "idle" | "loading" | "speaking" | "blocked" | "unavailable";

/** Keeps the utterance alive, waits for OS voices, and surfaces silent failures. */
export class MarvinVoice {
  private utterance: SpeechSynthesisUtterance | null = null;
  private generation = 0;
  private cleanup: (() => void) | null = null;
  private synth: SpeechSynthesis;
  private Utterance: typeof SpeechSynthesisUtterance;
  private onState: (state: VoiceState) => void;
  constructor(
    synth: SpeechSynthesis,
    Utterance: typeof SpeechSynthesisUtterance,
    onState: (state: VoiceState) => void,
  ) {
    this.synth = synth;
    this.Utterance = Utterance;
    this.onState = onState;
  }
  stop() {
    this.generation += 1;
    this.cleanup?.();
    this.cleanup = null;
    this.utterance = null;
    this.synth.cancel();
    this.onState("idle");
  }
  speak(text: string, locale: string) {
    this.stop();
    const generation = this.generation;
    this.onState("loading");
    let timer: ReturnType<typeof setTimeout>;
    const clear = () => {
      clearTimeout(timer);
      this.synth.removeEventListener("voiceschanged", start);
    };
    const start = () => {
      if (generation !== this.generation) return;
      clear();
      const voices = this.synth.getVoices();
      const language = locale.slice(0, 2).toLowerCase();
      const matching = voices.filter((voice) => voice.lang.toLowerCase().startsWith(language));
      const voice = matching.find((voice) => voice.localService) || matching[0] ||
        voices.find((voice) => voice.localService) || voices[0];
      if (!voice) { this.onState("unavailable"); return; }
      const utterance = new this.Utterance(text);
      this.utterance = utterance;
      utterance.voice = voice;
      utterance.lang = voice.lang;
      utterance.pitch = 0.68;
      utterance.rate = 0.78;
      utterance.volume = 0.88;
      const finish = (state: VoiceState) => {
        if (generation !== this.generation) return;
        clearTimeout(timer);
        this.utterance = null;
        this.onState(state);
      };
      utterance.onstart = () => {
        if (generation !== this.generation) return;
        clearTimeout(timer);
        this.onState("speaking");
      };
      utterance.onend = () => finish("idle");
      utterance.onerror = (event) => finish(
        event.error === "voice-unavailable" || event.error === "language-unavailable"
          ? "unavailable" : "blocked",
      );
      timer = setTimeout(() => {
        if (generation !== this.generation) return;
        this.generation += 1;
        this.synth.cancel();
        this.utterance = null;
        this.onState("blocked");
      }, 5000);
      try {
        this.synth.resume();
        this.synth.speak(utterance);
      } catch { finish("blocked"); }
    };
    this.cleanup = clear;
    if (this.synth.getVoices().length) start();
    else {
      this.synth.addEventListener("voiceschanged", start);
      timer = setTimeout(start, 1500);
    }
  }
}
