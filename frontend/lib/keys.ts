export type ScoreKey = {
  id: string;
  label: string;
};

export const SCORE_KEYS: ScoreKey[] = [
  { id: "C", label: "C" },
  { id: "Db", label: "bD" },
  { id: "D", label: "D" },
  { id: "Eb", label: "bE" },
  { id: "E", label: "E" },
  { id: "F", label: "F" },
  { id: "F#", label: "#F" },
  { id: "G", label: "G" },
  { id: "Ab", label: "bA" },
  { id: "A", label: "A" },
  { id: "Bb", label: "bB" },
  { id: "B", label: "B" },
];

export const DEFAULT_FROM_KEY = "C";
export const DEFAULT_TO_KEY = "G";
