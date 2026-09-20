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
        drawTitle: false,
        drawSubtitle: false,
        drawComposer: false,
        drawLyricist: false,
        drawCredits: false,
        drawPartNames: false,
        drawPartAbbreviations: false,
        drawMeasureNumbers: false,
        drawingParameters: "compacttight",
        pageFormat: "Endless",
      });
      await osmd.load(musicXml);
      if (cancelled || !ref.current) return;
      const rules = osmd.EngravingRules;
      if (rules) {
        rules.PageLeftMargin = 1.2;
        rules.PageRightMargin = 1.2;
        rules.PageTopMargin = 0.6;
        rules.PageBottomMargin = 0.8;
        rules.TitleTopDistance = 0;
        rules.SystemLeftMargin = 0;
      }
      const width = ref.current.clientWidth || 320;
      osmd.zoom = width < 560 ? Math.max(0.78, Math.min(0.96, width / 390)) : 1;
      osmd.render();
      if (cancelled || !ref.current) return;
      const svg = ref.current.querySelector("svg");
      if (svg) {
        try {
          const box = svg.getBBox();
          if (box.width > 0 && box.height > 0) {
            svg.setAttribute("viewBox", `0 0 ${box.width} ${box.height + 8}`);
            svg.setAttribute("height", String(Math.ceil(box.height + 8)));
            svg.style.height = `${Math.ceil(box.height + 8)}px`;
            svg.style.maxWidth = "100%";
          }
        } catch {
          // keep OSMD's page size if the SVG is not measurable yet
        }
      }
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

  return <div ref={ref} className="score-paper" />;
}
