"use client";

import { useEffect, useRef, useState } from "react";
import { armTunerAudio, stopTunerAudio } from "@/lib/tunerAudio";
import { detectPitch, pitchFromFrequency, type PitchReading } from "@/lib/pitch";

const A4_DEFAULT = 440;

export function TunerApp() {
  const [error, setError] = useState<string | null>(null);
  const [a4, setA4] = useState(A4_DEFAULT);
  const [reading, setReading] = useState<PitchReading | null>(null);
  const a4Ref = useRef(a4);
  const smoothedRef = useRef<number | null>(null);

  useEffect(() => {
    a4Ref.current = a4;
  }, [a4]);

  useEffect(() => {
    let cancelled = false;
    let frame = 0;

    const start = async () => {
      try {
        const { stream, context } = await armTunerAudio();
        if (cancelled) return;
        const source = context.createMediaStreamSource(stream);
        const analyser = context.createAnalyser();
        analyser.fftSize = 4096;
        source.connect(analyser);
        const buffer = new Float32Array(analyser.fftSize);
        setError(null);

        const tick = () => {
          if (cancelled) return;
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
          setError("打不开麦克风。");
        }
      }
    };

    void start();
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(frame);
      smoothedRef.current = null;
      setReading(null);
      void stopTunerAudio();
    };
  }, []);

  const cents = reading ? Math.max(-50, Math.min(50, reading.cents)) : 0;
  const inTune = Boolean(reading && Math.abs(reading.cents) <= 8);
  const side = !reading ? "等声音" : reading.cents < -8 ? "偏低" : reading.cents > 8 ? "偏高" : "准了";

  return (
    <div className="app-frame">
      <main className="work-panel">
        <header className="panel-heading">
          <h1>校音</h1>
        </header>

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
          {reading ? <p className={`tuner-side ${inTune ? "is-true" : ""}`}>{side}</p> : null}
          <div className="tuner-gauge" aria-hidden="true">
            <span className="tuner-gauge__track" />
            <span className="tuner-gauge__center" />
            <span
              className={`tuner-gauge__needle ${reading ? "is-on" : ""}`}
              style={{ left: `${50 + cents}%` }}
            />
          </div>
          {reading ? (
            <p className="tuner-meta">
              {reading.frequency.toFixed(1)} Hz · {reading.cents > 0 ? "+" : ""}
              {reading.cents}
            </p>
          ) : null}
        </section>

        <label className="slider-field">
          <span className="field-label">{a4}</span>
          <input
            type="range"
            min={415}
            max={466}
            value={a4}
            onChange={(event) => setA4(Number(event.target.value))}
          />
        </label>

        {error ? (
          <p className="error-message" role="alert">
            {error}
          </p>
        ) : null}
      </main>
    </div>
  );
}
