"use client";

type KeyChoice = {
  id: string;
  label: string;
  instrumentId: string;
  icon: string;
};

const KEY_CHOICES: KeyChoice[] = [
  { id: "C", label: "C", instrumentId: "piano", icon: "🎹" },
  { id: "Bb", label: "bB", instrumentId: "soprano_sax", icon: "🎷" },
  { id: "Eb", label: "bE", instrumentId: "alto_sax", icon: "🎷" },
  { id: "F", label: "F", instrumentId: "horn_f", icon: "🎺" },
];

const INSTRUMENT_TO_KEY: Record<string, string> = {
  piano: "C",
  flute: "C",
  oboe: "C",
  trombone: "C",
  tuba: "C",
  violin: "C",
  viola: "C",
  cello: "C",
  guitar: "C",
  clarinet_bb: "Bb",
  soprano_sax: "Bb",
  tenor_sax: "Bb",
  trumpet_bb: "Bb",
  alto_sax: "Eb",
  bari_sax: "Eb",
  horn_f: "F",
};

type Props = {
  value: string;
  disabled?: boolean;
  onChange: (id: string) => void;
};

export function keyLabelForInstrument(instrumentId: string) {
  const keyId = INSTRUMENT_TO_KEY[instrumentId] ?? "C";
  return KEY_CHOICES.find((item) => item.id === keyId)?.label ?? "C";
}

export function InstrumentPicker({ value, disabled, onChange }: Props) {
  const selectedKey = INSTRUMENT_TO_KEY[value] ?? "C";

  return (
    <div className="key-picker" role="radiogroup" aria-label="调性">
      {KEY_CHOICES.map((choice) => {
        const checked = choice.id === selectedKey;
        return (
          <button
            key={choice.id}
            type="button"
            role="radio"
            aria-checked={checked}
            aria-label={choice.label}
            className={`key-chip ${checked ? "is-selected" : ""}`}
            disabled={disabled}
            onClick={() => onChange(choice.instrumentId)}
          >
            <span className="key-chip__float" aria-hidden="true">
              <span className="key-chip__icon">{choice.icon}</span>
            </span>
            <span className="key-chip__label">{choice.label}</span>
          </button>
        );
      })}
    </div>
  );
}
