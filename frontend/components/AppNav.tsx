"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ArrowsLeftRight, Metronome, MusicNotesSimple, Waveform } from "@phosphor-icons/react";
import { armTunerAudio } from "@/lib/tunerAudio";

const ITEMS = [
  { href: "/tuner", label: "校音", Icon: Waveform },
  { href: "/metro", label: "节拍", Icon: Metronome },
  { href: "/", label: "扒谱", Icon: MusicNotesSimple },
  { href: "/transpose", label: "移调", Icon: ArrowsLeftRight },
] as const;

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="app-nav" aria-label="主要功能">
      {ITEMS.map(({ href, label, Icon }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`app-nav__item ${active ? "is-active" : ""}`}
            aria-current={active ? "page" : undefined}
            onClick={() => {
              if (href === "/tuner") void armTunerAudio();
            }}
          >
            <Icon className="app-nav__icon" weight={active ? "fill" : "regular"} />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
