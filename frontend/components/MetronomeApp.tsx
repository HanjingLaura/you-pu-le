"use client";

import { useEffect, useRef, useState } from "react";
import {
  metronomeContext,
  playMetronomeClick,
  suspendMetronomeAudio,
  unlockMetronomeAudio,
} from "@/lib/metroAudio";

type Meter = { id: string; beats: number; accents: number[] };

const METERS: Meter[] = [
  { id: "2/4", beats: 2, accents: [0] },
  { id: "3/4", beats: 3, accents: [0] },
  { id: "4/4", beats: 4, accents: [0] },
  { id: "6/8", beats: 6, accents: [0, 3] },
];

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
    return () => {
      stopMetronome();
    };
  }, []);

  function stopMetronome() {
    window.clearInterval(timerRef.current);
    timerRef.current = 0;
    runningRef.current = false;
    setRunning(false);
    setBeat(0);
    void suspendMetronomeAudio();
  }

  function schedule() {
    const context = metronomeContext();
    if (!context || !runningRef.current) return;
    if (context.state === "suspended") {
      void context.resume();
    }
    const meter = meterRef.current;
    while (nextTimeRef.current < context.currentTime + 0.18) {
      const current = beatIndexRef.current;
      playMetronomeClick(nextTimeRef.current, meter.accents.includes(current % meter.beats));
      const shown = current % meter.beats;
      const delay = Math.max(0, (nextTimeRef.current - context.currentTime) * 1000);
      window.setTimeout(() => {
        if (runningRef.current) setBeat(shown);
      }, delay);
      nextTimeRef.current += 60 / bpmRef.current;
      beatIndexRef.current += 1;
    }
  }

  async function startMetronome() {
    try {
      const context = await unlockMetronomeAudio();
      setError(null);
      runningRef.current = true;
      setRunning(true);
      setBeat(0);
      beatIndexRef.current = 1;
      nextTimeRef.current = context.currentTime + 60 / bpmRef.current;
      schedule();
      window.clearInterval(timerRef.current);
      timerRef.current = window.setInterval(schedule, 25);
    } catch (err) {
      runningRef.current = false;
      setRunning(false);
      setError(err instanceof Error ? err.message : "这个浏览器发不了声。");
    }
  }

  function toggleMetronome() {
    if (runningRef.current) {
      stopMetronome();
      return;
    }
    void startMetronome();
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
          <input
            type="range"
            min={30}
            max={240}
            value={bpm}
            aria-label="速度"
            onChange={(event) => setBpm(Number(event.target.value))}
          />
        </label>

        <div className="metro-stepper">
          <button type="button" className="text-button" onClick={() => setBpm((value) => clampBpm(value - 1))}>
            −1
          </button>
          <button type="button" className="text-button" onClick={tap}>
            拍速
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
