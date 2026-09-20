"use client";

import { useEffect, useRef, useState } from "react";

type Meter = { id: string; beats: number; accents: number[] };

const METERS: Meter[] = [
  { id: "2/4", beats: 2, accents: [0] },
  { id: "3/4", beats: 3, accents: [0] },
  { id: "4/4", beats: 4, accents: [0] },
  { id: "6/8", beats: 6, accents: [0, 3] },
];

function audioContextCtor(): typeof AudioContext | null {
  const fromWindow = window as Window & { webkitAudioContext?: typeof AudioContext };
  return window.AudioContext ?? fromWindow.webkitAudioContext ?? null;
}

function playClick(context: AudioContext, time: number, accent: boolean) {
  const sampleRate = context.sampleRate;
  const length = Math.floor(sampleRate * 0.05);
  const buffer = context.createBuffer(1, length, sampleRate);
  const data = buffer.getChannelData(0);
  const freq = accent ? 1480 : 980;
  const amp = accent ? 0.9 : 0.58;
  for (let index = 0; index < length; index += 1) {
    const elapsed = index / sampleRate;
    data[index] = Math.sin(2 * Math.PI * freq * elapsed) * Math.exp(-elapsed * 52) * amp;
  }
  const source = context.createBufferSource();
  const gain = context.createGain();
  source.buffer = buffer;
  gain.gain.setValueAtTime(1, time);
  source.connect(gain);
  gain.connect(context.destination);
  source.start(time);
}

export function MetronomeApp() {
  const [bpm, setBpm] = useState(96);
  const [meterId, setMeterId] = useState("4/4");
  const [running, setRunning] = useState(false);
  const [beat, setBeat] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const tapsRef = useRef<number[]>([]);
  const bpmRef = useRef(bpm);
  const meterRef = useRef(METERS[2]);
  const runningRef = useRef(false);
  const contextRef = useRef<AudioContext | null>(null);
  const timerRef = useRef(0);
  const nextTimeRef = useRef(0);
  const beatIndexRef = useRef(0);

  useEffect(() => {
    bpmRef.current = bpm;
  }, [bpm]);

  useEffect(() => {
    meterRef.current = METERS.find((item) => item.id === meterId) ?? METERS[2];
  }, [meterId]);

  useEffect(() => {
    return () => stopMetronome();
  }, []);

  function stopMetronome() {
    window.clearInterval(timerRef.current);
    timerRef.current = 0;
    const context = contextRef.current;
    contextRef.current = null;
    runningRef.current = false;
    setRunning(false);
    setBeat(0);
    if (context && context.state !== "closed") {
      void context.close();
    }
  }

  function schedule() {
    const context = contextRef.current;
    if (!context || context.state === "closed") return;
    if (context.state === "suspended") {
      void context.resume();
    }
    const meter = meterRef.current;
    while (nextTimeRef.current < context.currentTime + 0.16) {
      const current = beatIndexRef.current;
      playClick(context, nextTimeRef.current, meter.accents.includes(current % meter.beats));
      const shown = current % meter.beats;
      const delay = Math.max(0, (nextTimeRef.current - context.currentTime) * 1000);
      window.setTimeout(() => {
        if (runningRef.current) setBeat(shown);
      }, delay);
      nextTimeRef.current += 60 / bpmRef.current;
      beatIndexRef.current += 1;
    }
  }

  function startMetronome() {
    const Ctor = audioContextCtor();
    if (!Ctor) {
      setError("这个浏览器发不了声。");
      return;
    }
    setError(null);
    const context = new Ctor();
    contextRef.current = context;
    if (context.state === "suspended") {
      void context.resume();
    }
    runningRef.current = true;
    setRunning(true);
    setBeat(0);
    beatIndexRef.current = 0;
    nextTimeRef.current = context.currentTime;
    // First click must happen in this tap, or iOS keeps the context silent.
    playClick(context, context.currentTime, true);
    beatIndexRef.current = 1;
    nextTimeRef.current = context.currentTime + 60 / bpmRef.current;
    schedule();
    timerRef.current = window.setInterval(schedule, 25);
  }

  function toggleMetronome() {
    if (runningRef.current) {
      stopMetronome();
      return;
    }
    startMetronome();
  }

  function clampBpm(value: number) {
    return Math.max(30, Math.min(240, Math.round(value)));
  }

  function tap() {
    const now = performance.now();
    const recent = tapsRef.current.filter((item) => now - item < 2800);
    recent.push(now);
    tapsRef.current = recent;
    if (recent.length < 2) return;
    const span = recent[recent.length - 1] - recent[0];
    const interval = span / (recent.length - 1);
    setBpm(clampBpm(60000 / interval));
  }

  const meter = METERS.find((item) => item.id === meterId) ?? METERS[2];

  return (
    <div className="app-frame">
      <main className="work-panel">
        <header className="panel-heading">
          <h1>节拍</h1>
        </header>
        <p className="lede">本机发声，不经过服务器。点开始就会响，离开这一页就停。</p>

        <section className="metro-stage">
          <p className="metro-bpm">
            <span className="metro-bpm__num">{bpm}</span>
            <span className="metro-bpm__unit">BPM</span>
          </p>
          <div className="metro-beats" aria-hidden="true">
            {Array.from({ length: meter.beats }, (_, index) => (
              <span
                key={index}
                className={`metro-dot ${running && index === beat ? "is-now" : ""} ${meter.accents.includes(index) ? "is-accent" : ""}`}
              />
            ))}
          </div>
        </section>

        <label className="slider-field">
          <span className="field-label">速度</span>
          <input
            type="range"
            min={30}
            max={240}
            value={bpm}
            onChange={(event) => setBpm(Number(event.target.value))}
          />
        </label>

        <div className="metro-stepper">
          <button type="button" className="text-button" onClick={() => setBpm((value) => clampBpm(value - 1))}>
            −1
          </button>
          <button type="button" className="text-button" onClick={tap}>
            拍一下定速
          </button>
          <button type="button" className="text-button" onClick={() => setBpm((value) => clampBpm(value + 1))}>
            +1
          </button>
        </div>

        <div className="key-picker metro-meter" role="radiogroup" aria-label="拍号">
          {METERS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="radio"
              aria-checked={item.id === meterId}
              className={`key-chip ${item.id === meterId ? "is-selected" : ""}`}
              onClick={() => {
                setMeterId(item.id);
                setBeat(0);
              }}
            >
              <span className="key-chip__label">{item.id}</span>
            </button>
          ))}
        </div>

        <button type="button" className="action-button" onClick={toggleMetronome}>
          <span className="action-button__label">{running ? "停止" : "开始"}</span>
        </button>

        {error ? (
          <p className="error-message" role="alert">
            {error}
          </p>
        ) : null}
      </main>
    </div>
  );
}
