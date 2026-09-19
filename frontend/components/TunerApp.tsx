"use client";

import { useEffect, useRef, useState } from "react";
import { detectPitch, pitchFromFrequency, type PitchReading } from "@/lib/pitch";

const A4_DEFAULT = 440;

export function TunerApp() {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [a4, setA4] = useState(A4_DEFAULT);
  const [reading, setReading] = useState<PitchReading | null>(null);
  const a4Ref = useRef(a4);
  const smoothedRef = useRef<number | null>(null);

  useEffect(() => {
    a4Ref.current = a4;
  }, [a4]);

  useEffect(() => {
    if (!listening) return undefined;

    let cancelled = false;
    let context: AudioContext | null = null;
    let stream: MediaStream | null = null;
    let frame = 0;

    const start = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
        });
        context = new AudioContext();
        const source = context.createMediaStreamSource(stream);
        const analyser = context.createAnalyser();
        analyser.fftSize = 4096;
        source.connect(analyser);
        const buffer = new Float32Array(analyser.fftSize);

        const tick = () => {
          if (cancelled || !context) return;
          analyser.getFloatTimeDomainData(buffer);
          const raw = detectPitch(buffer, context.sampleRate);
          if (raw) {
            const previous = smoothedRef.current;
            const next = previous ? previous * 0.65 + raw * 0.35 : raw;
            smoothedRef.current = next;
            setReading(pitchFromFrequency(next, a4Ref.current));
          } else {
            smoothedRef.current = null;
            setReading(null);
          }
          frame = window.requestAnimationFrame(tick);
        };
        frame = window.requestAnimationFrame(tick);
      } catch {
        if (!cancelled) {
          setError("打不开麦克风。请允许浏览器使用麦克风后再试。");
          setListening(false);
        }
      }
    };

    start();
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
      stream?.getTracks().forEach((track) => track.stop());
      void context?.close();
    };
  }, [listening]);

  const cents = reading ? Math.max(-50, Math.min(50, reading.cents)) : 0;
  const inTune = Boolean(reading && Math.abs(reading.cents) <= 8);
  const side = !reading ? "等声音" : reading.cents < -8 ? "偏低" : reading.cents > 8 ? "偏高" : "准了";

  return (
    <div className="app-frame">
      <main className="work-panel">
        <header className="panel-heading">
          <h1>校音</h1>
        </header>
        <p className="lede">对着麦克风吹或拉一个长音。这是本机实时校音，不上传声音。</p>

        <section className="tuner-stage" aria-live="polite">
          <p className="tuner-note">
            {reading ? (
              <>
                <span className="tuner-note__name">{reading.name}</span>
                <span className="tuner-note__octave">{reading.octave}</span>
              </>
            ) : (
              <span className="tuner-note__idle">—</span>
            )}
          </p>
          <p className={`tuner-side ${inTune ? "is-true" : ""}`}>{side}</p>
          <div className="tuner-gauge" aria-hidden="true">
            <span className="tuner-gauge__track" />
            <span className="tuner-gauge__center" />
            <span
              className={`tuner-gauge__needle ${reading ? "is-on" : ""}`}
              style={{ left: `${50 + cents}%` }}
            />
          </div>
          <p className="tuner-meta">
            {reading
              ? `${reading.frequency.toFixed(1)} Hz · ${reading.cents > 0 ? "+" : ""}${reading.cents} 音分`
              : listening
                ? "在听"
                : "还没开始"}
          </p>
        </section>

        <label className="slider-field">
          <span className="field-label">A4 = {a4} Hz</span>
          <input
            type="range"
            min={415}
            max={466}
            value={a4}
            onChange={(event) => setA4(Number(event.target.value))}
          />
        </label>

        <button
          type="button"
          className="action-button"
          onClick={() => {
            setError(null);
            setReading(null);
            smoothedRef.current = null;
            setListening((current) => !current);
          }}
        >
          <span className="action-button__label">{listening ? "停止" : "开始听"}</span>
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
