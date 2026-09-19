const COORDS = [6, 17, 28, 39, 50];

function delayFor(column: number, row: number) {
  const spiral = ((column + row * 2) % 5) * 90;
  const ring = Math.max(Math.abs(column - 2), Math.abs(row - 2));
  if (ring === 0) return 0;
  if (ring === 1) return 280 + spiral * 0.55;
  return 620 + spiral * 0.85 + (column + row) * 40;
}

export function DotMatrixLoader({
  size = 20,
  className = "",
}: {
  size?: number;
  className?: string;
}) {
  const litDots = [];
  for (let row = 0; row < 5; row += 1) {
    for (let column = 0; column < 5; column += 1) {
      litDots.push({
        key: `${column}-${row}`,
        x: COORDS[column],
        y: COORDS[row],
        delay: delayFor(column, row),
        ring: Math.max(Math.abs(column - 2), Math.abs(row - 2)),
      });
    }
  }

  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 56 56"
      width={size}
      height={size}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <circle id="kp-dot-base" r="2.4" fill="currentColor" opacity="0.1" />
        <circle id="kp-dot-lit" r="3.1" fill="currentColor" />
      </defs>
      <style>{`
        .kp-dot-lit {
          opacity: 0;
          animation: kp-dot-flash 1700ms cubic-bezier(0.65, 0, 0.35, 1) infinite both;
        }
        .kp-dot-lit.kp-dot-ring-0 { animation-name: kp-dot-flash-core; }
        .kp-dot-lit.kp-dot-ring-1 { animation-name: kp-dot-flash-mid; }
        .kp-dot-lit.kp-dot-ring-2 { animation-name: kp-dot-flash-outer; }
        @keyframes kp-dot-flash-core {
          0%, 22%, 100% { opacity: 0.08; }
          34% { opacity: 1; }
          52% { opacity: 0.12; }
        }
        @keyframes kp-dot-flash-mid {
          0%, 18%, 100% { opacity: 0.06; }
          32% { opacity: 0.92; }
          50% { opacity: 0.1; }
        }
        @keyframes kp-dot-flash-outer {
          0%, 14%, 100% { opacity: 0.05; }
          30% { opacity: 0.78; }
          48% { opacity: 0.08; }
        }
        @media (prefers-reduced-motion: reduce) {
          .kp-dot-lit { animation: none; opacity: 0.4; }
        }
      `}</style>
      {COORDS.map((y) =>
        COORDS.map((x) => <use key={`base-${x}-${y}`} href="#kp-dot-base" x={x} y={y} />),
      )}
      {litDots.map((dot) => (
        <use
          key={dot.key}
          className={`kp-dot-lit kp-dot-ring-${dot.ring}`}
          href="#kp-dot-lit"
          x={dot.x}
          y={dot.y}
          style={{ animationDelay: `${Math.round(dot.delay)}ms` }}
        />
      ))}
    </svg>
  );
}
