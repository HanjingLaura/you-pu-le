"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const SPIDER_SRC = "/spider/Spider.htm";
const SPIDER_REPO = "https://github.com/lrusso/Spider";

export function SpiderSolitaire() {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const [open, setOpen] = useState(false);

  const close = useCallback(() => {
    setOpen(false);
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!open) return undefined;
    panelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [close, open]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        className="spider-trigger"
        aria-label="打开蜘蛛纸牌"
        title="蜘蛛纸牌"
        onClick={() => setOpen(true)}
      >
        🕷
      </button>

      {open ? (
        <div className="spider-layer">
          <button type="button" className="spider-backdrop" aria-label="关闭蜘蛛纸牌" onClick={close} />
          <section
            ref={panelRef}
            className="spider-window"
            role="dialog"
            aria-modal="true"
            aria-labelledby="spider-title"
            tabIndex={-1}
          >
            <header className="spider-titlebar">
              <div className="spider-titlebar__name">
                <span aria-hidden="true">🕷</span>
                <h2 id="spider-title">蜘蛛纸牌</h2>
              </div>
              <button type="button" aria-label="关闭蜘蛛纸牌" onClick={close}>
                ×
              </button>
            </header>
            <iframe
              className="spider-frame"
              title="蜘蛛纸牌"
              src={SPIDER_SRC}
              allow="autoplay"
            />
            <p className="spider-credit">
              开源项目{" "}
              <a href={SPIDER_REPO} target="_blank" rel="noreferrer">
                lrusso/Spider
              </a>
            </p>
          </section>
        </div>
      ) : null}
    </>
  );
}
