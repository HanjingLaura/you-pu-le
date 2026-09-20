"use client";

import { SCORE_KEYS } from "@/lib/keys";

type Props = {
  label: string;
  value: string;
  disabled?: boolean;
  onChange: (id: string) => void;
};

export function KeySelect({ label, value, disabled, onChange }: Props) {
  return (
    <div className="key-select">
      <p className="field-label">{label}</p>
      <div className="key-select__row" role="radiogroup" aria-label={label}>
        {SCORE_KEYS.map((key) => {
          const checked = key.id === value;
          return (
            <button
              key={key.id}
              type="button"
              role="radio"
              aria-checked={checked}
              aria-label={`${key.label} 调`}
              className={`key-chip ${checked ? "is-selected" : ""}`}
              disabled={disabled}
              onClick={() => onChange(key.id)}
            >
              <span className="key-chip__label">{key.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
