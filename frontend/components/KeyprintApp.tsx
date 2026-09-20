"use client";

import { DownloadSimple } from "@phosphor-icons/react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  API_BASE,
  DEFAULT_INSTRUMENT,
  createJob,
  getJob,
  getMusicXml,
  rescoreJob,
  type Job,
} from "@/lib/api";
import { DotMatrixLoader } from "./DotMatrixLoader";
import { InstrumentPicker } from "./InstrumentPicker";
import { ScoreViewer } from "./ScoreViewer";

const ACCEPT = ".mp4,.mov,.webm,.mkv,.wav,.mp3,.m4a,.flac,.ogg";

function formatSize(bytes: number) {
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

const STAGE_PROGRESS: Record<string, number> = {
  queued: 6,
  downloading: 18,
  extracting: 32,
  transcribing: 62,
  scoring: 88,
  done: 100,
};

export function KeyprintApp() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");
  const [dragging, setDragging] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [musicXml, setMusicXml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [rescoring, setRescoring] = useState(false);
  const [instrumentId, setInstrumentId] = useState(DEFAULT_INSTRUMENT);

  const busy = submitting || Boolean(job && job.stage !== "done" && job.stage !== "error");
  const canSubmit = Boolean(file || url.trim()) && !busy;
  const progressLabel = Math.min(99, Math.max(0, Math.round(progress)));

  useEffect(() => {
    if (!job || job.stage === "done" || job.stage === "error") return;
    const jobId = job.id;
    const timer = window.setInterval(async () => {
      try {
        const next = await getJob(jobId);
        setJob(next);
        setProgress((current) => Math.max(current, STAGE_PROGRESS[next.stage] ?? current));
        if (next.stage === "error") {
          setError(next.error || "转录失败");
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : "无法读取任务状态";
        setError(message === "找不到这个任务。" ? "处理中断了，请再扒一次。" : message);
        setJob((current) =>
          current && current.id === jobId
            ? { ...current, stage: "error", error: message, message: "失败" }
            : current,
        );
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [job]);

  useEffect(() => {
    if (!job || job.stage !== "done" || job.id === "demo") return;
    let cancelled = false;
    getMusicXml(job.id)
      .then((xml) => {
        if (!cancelled) {
          setMusicXml(xml);
          setProgress(100);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "读不到 MusicXML");
      });
    return () => {
      cancelled = true;
    };
  }, [job]);

  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => {
      setProgress((current) => Math.min(92, current + Math.max(1, Math.ceil((92 - current) * 0.08))));
    }, 900);
    return () => window.clearInterval(timer);
  }, [busy]);

  function chooseFile(next?: File) {
    if (!next || busy) return;
    setError(null);
    setFile(next);
    setUrl("");
    setJob(null);
    setMusicXml(null);
  }

  async function submit() {
    if (!canSubmit) return;
    setError(null);
    setMusicXml(null);
    setSubmitting(true);
    setProgress(4);
    try {
      const created = await createJob(file ?? undefined, file ? undefined : url.trim(), instrumentId);
      setJob(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
      setProgress(0);
      setJob(null);
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setFile(null);
    setUrl("");
    setJob(null);
    setMusicXml(null);
    setError(null);
    setProgress(0);
    setSubmitting(false);
    setRescoring(false);
  }

  async function changeInstrument(nextId: string) {
    if (!job || job.stage !== "done" || nextId === job.instrument || rescoring) return;
    setInstrumentId(nextId);
    if (job.id === "demo") {
      setError(null);
      try {
        const response = await fetch(
          `${API_BASE}/demo/musicxml?instrument=${encodeURIComponent(nextId)}`,
          { cache: "no-store" },
        );
        if (!response.ok) throw new Error("示例谱读不到");
        const xml = await response.text();
        setJob({ ...job, instrument: nextId });
        setMusicXml(xml);
      } catch (err) {
        setError(err instanceof Error ? err.message : "示例谱读不到");
      }
      return;
    }
    setRescoring(true);
    setError(null);
    try {
      const updated = await rescoreJob(job.id, nextId);
      const xml = await getMusicXml(updated.id);
      setJob(updated);
      setMusicXml(xml);
    } catch (err) {
      setInstrumentId(job.instrument);
      setError(err instanceof Error ? err.message : "换乐器失败");
    } finally {
      setRescoring(false);
    }
  }

  const actionLabel = useMemo(() => {
    if (error) return "再试一次";
    return "扒一下";
  }, [error]);

  if (musicXml && job?.stage === "done") {
    return (
      <div className="result-shell">
        <div className="result-bar">
          <div>
            <p className="result-bar__brand">有谱了</p>
          </div>
          <div className="result-bar__actions">
            <InstrumentPicker
              value={job.instrument || instrumentId}
              disabled={rescoring}
              onChange={changeInstrument}
            />
            {job.id !== "demo" ? (
              <>
                <a className="download-button ghost" href={`${API_BASE}/jobs/${job.id}/midi`}>
                  <DownloadSimple className="size-4" />
                  MIDI
                </a>
                <a className="download-button" href={`${API_BASE}/jobs/${job.id}/musicxml`}>
                  <DownloadSimple className="size-4" />
                  MusicXML
                </a>
              </>
            ) : null}
            <button type="button" className="text-button" onClick={reset}>
              再来一次
            </button>
          </div>
        </div>
        {error ? (
          <p className="error-message result-error" role="alert">
            {error}
          </p>
        ) : null}
        <ScoreViewer musicXml={musicXml} />
      </div>
    );
  }

  return (
    <div className="app-frame">
      <main className="work-panel">
        <header className="panel-heading">
          <h1>有谱了</h1>
        </header>

        <form
          className="work-form"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <input
            ref={inputRef}
            className="file-upload__input"
            type="file"
            accept={ACCEPT}
            onChange={(event) => {
              chooseFile(event.target.files?.[0]);
              event.currentTarget.value = "";
            }}
          />

          <button
            type="button"
            className={`drop-well ${dragging ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
            aria-label="放入文件"
            disabled={busy}
            onClick={() => inputRef.current?.click()}
            onDragEnter={(event) => {
              event.preventDefault();
              if (!busy) setDragging(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              if (!busy) setDragging(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              if (!event.currentTarget.contains(event.relatedTarget as Node)) {
                setDragging(false);
              }
            }}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              chooseFile(event.dataTransfer.files[0]);
            }}
          >
            <span className="drop-well__staff" aria-hidden="true" />
            {file ? (
              <span className="drop-well__file">
                <span className="drop-well__name">{file.name}</span>
                <span className="drop-well__meta">{formatSize(file.size)}</span>
              </span>
            ) : null}
          </button>

          <label className="link-field">
            <input
              value={url}
              disabled={busy || Boolean(file)}
              aria-label="链接"
              onChange={(event) => {
                setUrl(event.target.value);
                setFile(null);
                setError(null);
                setJob(null);
              }}
              placeholder="链接"
            />
          </label>

          <InstrumentPicker
            value={instrumentId}
            disabled={busy}
            onChange={setInstrumentId}
          />

          <button
            type="submit"
            className={`action-button ${busy ? "processing" : ""}`}
            disabled={!canSubmit}
          >
            <span
              className="action-button__fill"
              style={{ transform: `scaleX(${busy ? Math.min(progress, 100) / 100 : 0})` }}
              aria-hidden="true"
            />
            <span className="action-button__label">
              {busy ? (
                <>
                  <DotMatrixLoader size={20} className="action-button__loader" />
                  <span className="action-button__percent">
                    <span className="action-button__percent-num">{progressLabel}</span>
                    <span className="action-button__percent-sign">%</span>
                  </span>
                  <span className="sr-only">{job?.message || "处理中"}</span>
                </>
              ) : (
                actionLabel
              )}
            </span>
          </button>

          {error ? (
            <p className="error-message" role="alert">
              {error}
            </p>
          ) : null}
        </form>
      </main>
    </div>
  );
}
