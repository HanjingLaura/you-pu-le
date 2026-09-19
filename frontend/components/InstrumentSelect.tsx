"use client";

import { useEffect, useMemo, useState } from "react";
import { DEFAULT_INSTRUMENT, FALLBACK_INSTRUMENTS, listInstruments, type Instrument } from "@/lib/api";

type Props = {
  label: string;
  value: string;
  items?: Instrument[];
  disabled?: boolean;
  onChange: (id: string) => void;
};

export function InstrumentSelect({ label, value, items: itemsProp, disabled, onChange }: Props) {
  const [items, setItems] = useState<Instrument[]>(itemsProp?.length ? itemsProp : FALLBACK_INSTRUMENTS);

  useEffect(() => {
    if (itemsProp?.length) {
      setItems(itemsProp);
      return;
    }
    let cancelled = false;
    listInstruments().then((next) => {
      if (!cancelled && next.length) setItems(next);
    });
    return () => {
      cancelled = true;
    };
  }, [itemsProp]);

  const groups = useMemo(() => {
    const map = new Map<string, Instrument[]>();
    for (const item of items) {
      const list = map.get(item.group) ?? [];
      list.push(item);
      map.set(item.group, list);
    }
    return [...map.entries()];
  }, [items]);

  const current = items.find((item) => item.id === value) ?? items.find((item) => item.id === DEFAULT_INSTRUMENT);

  return (
    <label className="link-field">
      <span className="field-label">{label}</span>
      <select
        className="instrument-select"
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
      >
        {groups.map(([group, groupItems]) => (
          <optgroup key={group} label={group}>
            {groupItems.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.key_label} · {item.staff_label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {current ? <span className="field-hint">{current.hint}</span> : null}
    </label>
  );
}
