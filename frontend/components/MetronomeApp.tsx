"use client";

import { useEffect, useRef, useState } from "react";

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
  const tapsRef = useRef<number[]>([]);
  const bpmRef = useRef(bpm);
  const meterRef = useRef(METERS[2]);

  useEffect(() => {
    bpmRef.current = bpm;
  }, [bpm]);

  useEffect(() => {
    meterRef.current = METERS.find((item) => item.id === meterId) ?? METERS[2];
  }, [meterId]);

  useEffect(() => {
    if (!running) return undefined;

    const context = new AudioContext();
    let nextTime = context.currentTime + 0.08;
    let beatIndex = 0;
    let timer = 0;

    const click = (time: number, accent: boolean) => {
      const osc = context.createOscillator();
      const gain = context.createGain();
      osc.type = "square";
      osc.frequency.setValueAtTime(accent ? 1320 : 880, time);
      gain.gain.setValueAtTime(0.0001, time);
      gain.gain.exponentialRampToValueAtTime(accent ? 0.22 : 0.12, time + 0.002);
      gain.gain.exponentialRampToValueAtTime(0.0001, time + 0.06);
      osc.connect(gain);
      gain.connect(context.destination);
      osc.start(time);
      osc.stop(time + 0.07);
    };

    const schedule = () => {
      const meter = meterRef.current;
      while (nextTime < context.currentTime + 0.12) {
        const current = beatIndex;
        click(nextTime, meter.accents.includes(current % meter.beats));
        window.setTimeout(() => setBeat(current % meter.beats), Math.max(0, (nextTime - context.currentTime) * 1000));
        nextTime += 60 / bpmRef.current;
        beatIndex += 1;
      }
    };

    schedule();
    timer = window.setInterval(schedule, 25);
    return () => {
      window.clearInterval(timer);
      void context.close();
    };
  }, [running]);

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
        <p className="lede">本机发声，不经过服务器。闪灯节拍器请用手机系统手电筒，这里只做听得见的拍点。</p>

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

        <button
          type="button"
          className="action-button"
          onClick={() => {
            setBeat(0);
            setRunning((current) => !current);
          }}
        >
          <span className="action-button__label">{running ? "停止" : "开始"}</span>
        </button>
      </main>
    </div>
  );
}
