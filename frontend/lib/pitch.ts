const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];

export type PitchReading = {
  frequency: number;
  midi: number;
  name: string;
  octave: number;
  cents: number;
};

export function pitchFromFrequency(frequency: number, a4 = 440): PitchReading | null {
  if (frequency < 50 || frequency > 2000) return null;
  const midiFloat = 69 + 12 * Math.log2(frequency / a4);
  const midi = Math.round(midiFloat);
  if (midi < 21 || midi > 108) return null;
  const cents = Math.round((midiFloat - midi) * 100);
  return {
    frequency,
    midi,
    name: NOTE_NAMES[(midi + 1200) % 12],
    octave: Math.floor(midi / 12) - 1,
    cents,
  };
}

export function detectPitch(buffer: Float32Array, sampleRate: number): number | null {
  const size = buffer.length;
  let rms = 0;
  for (let index = 0; index < size; index += 1) {
    rms += buffer[index] * buffer[index];
  }
  rms = Math.sqrt(rms / size);
  if (rms < 0.012) return null;

  const minLag = Math.floor(sampleRate / 2000);
  const maxLag = Math.min(size - 2, Math.floor(sampleRate / 50));
  let bestLag = -1;
  let bestCorr = 0;
  const norm = rms * rms * size || 1;

  for (let lag = minLag; lag <= maxLag; lag += 1) {
    let corr = 0;
    for (let index = 0; index < size - lag; index += 1) {
      corr += buffer[index] * buffer[index + lag];
    }
    const value = corr / norm;
    if (value > bestCorr) {
      bestCorr = value;
      bestLag = lag;
    }
  }

  if (bestLag < 1 || bestCorr < 0.28) return null;

  const y1 = autocorrelationAt(buffer, bestLag - 1);
  const y2 = autocorrelationAt(buffer, bestLag);
  const y3 = autocorrelationAt(buffer, bestLag + 1);
  const denom = 2 * (2 * y2 - y1 - y3);
  const shift = denom === 0 ? 0 : (y3 - y1) / denom;
  const period = bestLag + (Number.isFinite(shift) ? shift : 0);
  const frequency = sampleRate / period;
  if (frequency < 50 || frequency > 2000) return null;
  return frequency;
}

function autocorrelationAt(buffer: Float32Array, lag: number): number {
  if (lag < 0 || lag >= buffer.length) return 0;
  let sum = 0;
  for (let index = 0; index < buffer.length - lag; index += 1) {
    sum += buffer[index] * buffer[index + lag];
  }
  return sum;
}
