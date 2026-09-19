from __future__ import annotations

from dataclasses import dataclass

from music21 import clef, instrument


@dataclass(frozen=True)
class InstrumentSpec:
    id: str
    name: str
    group: str
    key_label: str
    staff_label: str
    write_semitones: int
    grand: bool
    clef: str
    sounding_low: int | None
    sounding_high: int | None
    hint: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "group": self.group,
            "key_label": self.key_label,
            "staff_label": self.staff_label,
            "write_semitones": self.write_semitones,
            "grand": self.grand,
            "clef": self.clef,
            "hint": self.hint,
        }


INSTRUMENTS: tuple[InstrumentSpec, ...] = (
    InstrumentSpec("piano", "钢琴", "键盘", "C", "大谱表", 0, True, "grand", 21, 108, "双手，高音谱号 + 低音谱号，按实音记谱。"),
    InstrumentSpec("flute", "长笛", "木管", "C", "高音谱号", 0, False, "treble", 60, 96, "C 调，按实音记谱。"),
    InstrumentSpec("oboe", "双簧管", "木管", "C", "高音谱号", 0, False, "treble", 58, 91, "C 调，按实音记谱。"),
    InstrumentSpec("clarinet_bb", "单簧管", "木管", "降B", "高音谱号 · 移调", 2, False, "treble", 50, 86, "降B 调。写成比实音高一个大二度。"),
    InstrumentSpec("soprano_sax", "高音萨克斯", "木管", "降B", "高音谱号 · 移调", 2, False, "treble", 56, 87, "降B 调。写成比实音高一个大二度。"),
    InstrumentSpec("alto_sax", "中音萨克斯", "木管", "降E", "高音谱号 · 移调", 9, False, "treble", 49, 81, "降E 调。写成比实音高一个大六度。"),
    InstrumentSpec("tenor_sax", "次中音萨克斯", "木管", "降B", "高音谱号 · 移调", 14, False, "treble", 44, 76, "降B 调。写成比实音高一个大九度。"),
    InstrumentSpec("bari_sax", "上低音萨克斯", "木管", "降E", "高音谱号 · 移调", 21, False, "treble", 36, 69, "降E 调。写成比实音高一个八度加一个大六度。"),
    InstrumentSpec("trumpet_bb", "小号", "铜管", "降B", "高音谱号 · 移调", 2, False, "treble", 54, 86, "降B 调。写成比实音高一个大二度。"),
    InstrumentSpec("horn_f", "圆号", "铜管", "F", "高音谱号 · 移调", 7, False, "treble", 41, 77, "F 调。写成比实音高一个纯五度。"),
    InstrumentSpec("trombone", "长号", "铜管", "C", "低音谱号", 0, False, "bass", 40, 72, "C 调，按实音记谱。"),
    InstrumentSpec("tuba", "大号", "铜管", "C", "低音谱号", 0, False, "bass", 28, 58, "C 调，按实音记谱。"),
    InstrumentSpec("violin", "小提琴", "弦乐", "C", "高音谱号", 0, False, "treble", 55, 96, "C 调，按实音记谱。"),
    InstrumentSpec("viola", "中提琴", "弦乐", "C", "中音谱号", 0, False, "alto", 48, 84, "C 调，按实音记谱。"),
    InstrumentSpec("cello", "大提琴", "弦乐", "C", "低音谱号", 0, False, "bass", 36, 76, "C 调，按实音记谱。"),
    InstrumentSpec("guitar", "吉他", "弦乐", "C", "高音谱号 8va", 12, False, "treble8vb", 40, 76, "C 调。高音谱号，写成比实音高一个八度。"),
)

DEFAULT_INSTRUMENT = "piano"
_BY_ID = {item.id: item for item in INSTRUMENTS}


def get_instrument(instrument_id: str | None) -> InstrumentSpec:
    if not instrument_id:
        return _BY_ID[DEFAULT_INSTRUMENT]
    spec = _BY_ID.get(instrument_id)
    if spec is None:
        raise ValueError("没有这个乐器。")
    return spec


def list_instruments() -> list[dict]:
    return [item.to_dict() for item in INSTRUMENTS]


def music21_instrument(spec: InstrumentSpec):
    mapping = {
        "piano": instrument.Piano,
        "flute": instrument.Flute,
        "oboe": instrument.Oboe,
        "clarinet_bb": instrument.Clarinet,
        "soprano_sax": instrument.SopranoSaxophone,
        "alto_sax": instrument.AltoSaxophone,
        "tenor_sax": instrument.TenorSaxophone,
        "bari_sax": instrument.BaritoneSaxophone,
        "trumpet_bb": instrument.Trumpet,
        "horn_f": instrument.Horn,
        "trombone": instrument.Trombone,
        "tuba": instrument.Tuba,
        "violin": instrument.Violin,
        "viola": instrument.Viola,
        "cello": instrument.Violoncello,
        "guitar": instrument.AcousticGuitar,
    }
    return mapping[spec.id]()


def music21_clef(spec: InstrumentSpec):
    mapping = {
        "treble": clef.TrebleClef,
        "bass": clef.BassClef,
        "alto": clef.AltoClef,
        "tenor": clef.TenorClef,
        "treble8vb": clef.Treble8vbClef,
    }
    return mapping[spec.clef]()
