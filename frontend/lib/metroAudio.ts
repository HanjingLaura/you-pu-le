const SILENT_WAV =
  "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";

type AudioWindow = Window & { webkitAudioContext?: typeof AudioContext };

let context: AudioContext | null = null;
let silent: HTMLAudioElement | null = null;
let master: GainNode | null = null;

function audioContextCtor(): typeof AudioContext | null {
  const fromWindow = window as AudioWindow;
  return window.AudioContext ?? fromWindow.webkitAudioContext ?? null;
}

function setPlaybackSession() {
  const session = (navigator as Navigator & { audioSession?: { type: string } }).audioSession;
  if (session) session.type = "playback";
}

function ensureSilentPlayer() {
  if (silent) return silent;
  const player = new Audio(SILENT_WAV);
  player.loop = true;
  player.preload = "auto";
  player.setAttribute("playsinline", "true");
  player.volume = 0.01;
  silent = player;
  return player;
}

export function playMetronomeClick(time: number, accent: boolean) {
  if (!context || !master || context.state === "closed") return;
  const when = Math.max(time, context.currentTime + 0.002);
  const osc = context.createOscillator();
  const gain = context.createGain();
  osc.type = "square";
  osc.frequency.setValueAtTime(accent ? 1046 : 698, when);
  const peak = accent ? 0.42 : 0.28;
  gain.gain.setValueAtTime(0.0001, when);
  gain.gain.exponentialRampToValueAtTime(peak, when + 0.004);
  gain.gain.exponentialRampToValueAtTime(0.0001, when + (accent ? 0.07 : 0.05));
  osc.connect(gain);
  gain.connect(master);
  osc.start(when);
  osc.stop(when + 0.09);
}

export async function unlockMetronomeAudio(): Promise<AudioContext> {
  const Ctor = audioContextCtor();
  if (!Ctor) {
    throw new Error("这个浏览器发不了声。");
  }
  setPlaybackSession();
  if (!context || context.state === "closed") {
    context = new Ctor();
    master = context.createGain();
    master.gain.value = 1;
    master.connect(context.destination);
  }
  const output = master;
  if (!context || !output) {
    throw new Error("这个浏览器发不了声。");
  }
  const player = ensureSilentPlayer();
  try {
    player.currentTime = 0;
    void player.play();
  } catch {
    // HTML audio unlock is best-effort; Web Audio still continues.
  }
  void context.resume();
  const poke = context.createOscillator();
  const pokeGain = context.createGain();
  pokeGain.gain.value = 0.0001;
  poke.connect(pokeGain);
  pokeGain.connect(output);
  poke.start();
  poke.stop(context.currentTime + 0.03);
  if (context.state !== "running") {
    await context.resume();
  }
  playMetronomeClick(context.currentTime, true);
  return context;
}

export async function suspendMetronomeAudio(): Promise<void> {
  if (silent) {
    silent.pause();
  }
  if (context && context.state === "running") {
    await context.suspend();
  }
}

export function metronomeContext(): AudioContext | null {
  return context && context.state !== "closed" ? context : null;
}
