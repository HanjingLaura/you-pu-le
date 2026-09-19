export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type JobStage =
  | "queued"
  | "downloading"
  | "extracting"
  | "transcribing"
  | "scoring"
  | "done"
  | "error";

export type Instrument = {
  id: string;
  name: string;
  group: string;
  key_label: string;
  staff_label: string;
  write_semitones: number;
  grand: boolean;
  clef: string;
  hint: string;
};

export type Job = {
  id: string;
  filename: string;
  stage: JobStage;
  message: string;
  error: string | null;
  created_at: string;
  duration_sec: number | null;
  note_count: number | null;
  pedal_count: number | null;
  key_name: string | null;
  bpm: number | null;
  instrument: string;
  midi_url: string | null;
  musicxml_url: string | null;
};

export const FALLBACK_INSTRUMENTS: Instrument[] = [
  { id: "piano", name: "钢琴", group: "键盘", key_label: "C", staff_label: "大谱表", write_semitones: 0, grand: true, clef: "grand", hint: "双手，高音谱号 + 低音谱号，按实音记谱。" },
  { id: "flute", name: "长笛", group: "木管", key_label: "C", staff_label: "高音谱号", write_semitones: 0, grand: false, clef: "treble", hint: "C 调，按实音记谱。" },
  { id: "oboe", name: "双簧管", group: "木管", key_label: "C", staff_label: "高音谱号", write_semitones: 0, grand: false, clef: "treble", hint: "C 调，按实音记谱。" },
  { id: "clarinet_bb", name: "单簧管", group: "木管", key_label: "降B", staff_label: "高音谱号 · 移调", write_semitones: 2, grand: false, clef: "treble", hint: "降B 调。写成比实音高一个大二度。" },
  { id: "soprano_sax", name: "高音萨克斯", group: "木管", key_label: "降B", staff_label: "高音谱号 · 移调", write_semitones: 2, grand: false, clef: "treble", hint: "降B 调。写成比实音高一个大二度。" },
  { id: "alto_sax", name: "中音萨克斯", group: "木管", key_label: "降E", staff_label: "高音谱号 · 移调", write_semitones: 9, grand: false, clef: "treble", hint: "降E 调。写成比实音高一个大六度。" },
  { id: "tenor_sax", name: "次中音萨克斯", group: "木管", key_label: "降B", staff_label: "高音谱号 · 移调", write_semitones: 14, grand: false, clef: "treble", hint: "降B 调。写成比实音高一个大九度。" },
  { id: "bari_sax", name: "上低音萨克斯", group: "木管", key_label: "降E", staff_label: "高音谱号 · 移调", write_semitones: 21, grand: false, clef: "treble", hint: "降E 调。写成比实音高一个八度加一个大六度。" },
  { id: "trumpet_bb", name: "小号", group: "铜管", key_label: "降B", staff_label: "高音谱号 · 移调", write_semitones: 2, grand: false, clef: "treble", hint: "降B 调。写成比实音高一个大二度。" },
  { id: "horn_f", name: "圆号", group: "铜管", key_label: "F", staff_label: "高音谱号 · 移调", write_semitones: 7, grand: false, clef: "treble", hint: "F 调。写成比实音高一个纯五度。" },
  { id: "trombone", name: "长号", group: "铜管", key_label: "C", staff_label: "低音谱号", write_semitones: 0, grand: false, clef: "bass", hint: "C 调，按实音记谱。" },
  { id: "tuba", name: "大号", group: "铜管", key_label: "C", staff_label: "低音谱号", write_semitones: 0, grand: false, clef: "bass", hint: "C 调，按实音记谱。" },
  { id: "violin", name: "小提琴", group: "弦乐", key_label: "C", staff_label: "高音谱号", write_semitones: 0, grand: false, clef: "treble", hint: "C 调，按实音记谱。" },
  { id: "viola", name: "中提琴", group: "弦乐", key_label: "C", staff_label: "中音谱号", write_semitones: 0, grand: false, clef: "alto", hint: "C 调，按实音记谱。" },
  { id: "cello", name: "大提琴", group: "弦乐", key_label: "C", staff_label: "低音谱号", write_semitones: 0, grand: false, clef: "bass", hint: "C 调，按实音记谱。" },
  { id: "guitar", name: "吉他", group: "弦乐", key_label: "C", staff_label: "高音谱号 8va", write_semitones: 12, grand: false, clef: "treble8vb", hint: "C 调。高音谱号，写成比实音高一个八度。" },
];

export const DEFAULT_INSTRUMENT = "piano";

export async function listInstruments(): Promise<Instrument[]> {
  try {
    const response = await fetch(`${API_BASE}/instruments`, { cache: "no-store" });
    if (!response.ok) return FALLBACK_INSTRUMENTS;
    const payload = (await response.json()) as { items?: Instrument[] };
    return payload.items?.length ? payload.items : FALLBACK_INSTRUMENTS;
  } catch {
    return FALLBACK_INSTRUMENTS;
  }
}

export async function createJob(file?: File, url?: string, instrument?: string): Promise<Job> {
  const body = new FormData();
  if (file) body.append("file", file);
  if (url) body.append("url", url);
  if (instrument) body.append("instrument", instrument);
  const response = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    body,
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function getJob(id: string): Promise<Job> {
  const response = await fetch(`${API_BASE}/jobs/${id}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

export async function getMusicXml(id: string): Promise<string> {
  const response = await fetch(`${API_BASE}/jobs/${id}/musicxml-text`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.text();
}

export async function rescoreJob(id: string, instrument: string): Promise<Job> {
  const body = new FormData();
  body.append("instrument", instrument);
  const response = await fetch(`${API_BASE}/jobs/${id}/rescore`, {
    method: "POST",
    body,
  });
  if (!response.ok) {
    throw new Error(await readError(response));
  }
  return response.json();
}

async function readError(response: Response): Promise<string> {
  const text = await response.text();
  try {
    const json = JSON.parse(text) as { detail?: string };
    if (json.detail) return json.detail;
  } catch {
    // keep raw text
  }
  return text || `请求失败（${response.status}）`;
}
