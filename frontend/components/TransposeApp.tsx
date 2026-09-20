"use client";

import { DownloadSimple } from "@phosphor-icons/react";
import { useRef, useState } from "react";
import {
  API_BASE,
  getMusicXml,
  inspectScoreKey,
  retranposeJob,
  transposeScore,
  type TransposeJob,
} from "@/lib/api";
import { DEFAULT_FROM_KEY, DEFAULT_TO_KEY } from "@/lib/keys";
import { DotMatrixLoader } from "./DotMatrixLoader";
import { KeySelect } from "./KeySelect";
import { ScoreViewer } from "./ScoreViewer";

const ACCEPT = ".musicxml,.xml,.mxl,.mid,.midi";

function formatSize(bytes: number) {
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function TransposeApp() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [job, setJob] = useState<TransposeJob | null>(null);
  const [musicXml, setMusicXml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fromKey, setFromKey] = useState(DEFAULT_FROM_KEY);
  const [toKey, setToKey] = useState(DEFAULT_TO_KEY);

  const busy = submitting;
  const canSubmit = Boolean(file) && !busy;

  function chooseFile(next?: File) {
    if (!next || busy) return;
    setError(null);
    setFile(next);
    setJob(null);
    setMusicXml(null);
    void inspectScoreKey(next).then((key) => {
      if (key) setFromKey(key);
    });
  }

  async function submit() {
    if (!file || !canSubmit) return;
    setError(null);
    setMusicXml(null);
    setSubmitting(true);
    try {
      const created = await transposeScore(file, fromKey, toKey);
      const xml = await getMusicXml(created.id);
      setJob(created);
      setMusicXml(xml);
    } catch (err) {
      setError(err instanceof Error ? err.message : "移调失败");
      setJob(null);
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setFile(null);
    setJob(null);
    setMusicXml(null);
    setError(null);
    setSubmitting(false);
  }

  async function changeTarget(nextId: string) {
    if (!job || job.stage !== "done" || nextId === (job.to_key || toKey) || submitting) return;
    setToKey(nextId);
    setSubmitting(true);
    setError(null);
    try {
      const updated = await retranposeJob(job.id, nextId);
      const xml = await getMusicXml(updated.id);
      setJob(updated);
      setMusicXml(xml);
    } catch (err) {
      setToKey(job.to_key || toKey);
      setError(err instanceof Error ? err.message : "移调失败");
    } finally {
      setSubmitting(false);
    }
  }

  if (musicXml && job?.stage === "done") {
    return (
      <div className="app-frame">
        <div className="result-shell">
          <div className="result-bar">
            <KeySelect label="移到" value={job.to_key || toKey} disabled={submitting} onChange={changeTarget} />
            <div className="result-bar__actions">
              <a className="download-button ghost" href={`${API_BASE}/jobs/${job.id}/midi`}>
                <DownloadSimple className="size-4" />
                MIDI
              </a>
              <a className="download-button" href={`${API_BASE}/jobs/${job.id}/musicxml`}>
                <DownloadSimple className="size-4" />
                MusicXML
              </a>
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
      </div>
    );
  }

  return (
    <div className="app-frame">
      <main className="work-panel">
        <header className="panel-heading">
          <h1>移调</h1>
        </header>

        <form
          className="work-form"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
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
            aria-label="上传谱子"
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

          <KeySelect label="原调" value={fromKey} disabled={busy} onChange={setFromKey} />
          <KeySelect label="移到" value={toKey} disabled={busy} onChange={setToKey} />

          <button type="submit" className={`action-button ${busy ? "processing" : ""}`} disabled={!canSubmit}>
            <span className="action-button__label">
              {busy ? (
                <>
                  <DotMatrixLoader size={20} className="action-button__loader" />
                  <span className="sr-only">正在移调</span>
                </>
              ) : (
                "移一下"
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
