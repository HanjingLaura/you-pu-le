"use client";

import { useEffect, useRef } from "react";

type ScoreViewerProps = {
  musicXml: string;
};

export function ScoreViewer({ musicXml }: ScoreViewerProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = ref.current;
    if (!container || !musicXml) return;

    let cancelled = false;
    container.replaceChildren();

    const render = async () => {
      const { OpenSheetMusicDisplay } = await import("opensheetmusicdisplay");
      if (cancelled || !ref.current) return;
      const osmd = new OpenSheetMusicDisplay(ref.current, {
        backend: "svg",
        autoResize: true,
        drawTitle: true,
        drawComposer: true,
        drawingParameters: "compact",
      });
      await osmd.load(musicXml);
      if (cancelled) return;
      osmd.render();
    };

    render().catch((error: unknown) => {
      if (cancelled || !ref.current) return;
      ref.current.textContent =
        error instanceof Error ? error.message : "乐谱渲染失败";
    });

    return () => {
      cancelled = true;
      container.replaceChildren();
    };
  }, [musicXml]);

  return <div ref={ref} className="score-paper w-full px-5 py-8" />;
}
