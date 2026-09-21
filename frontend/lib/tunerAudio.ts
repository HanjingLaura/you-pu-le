type TunerSession = {
  stream: MediaStream;
  context: AudioContext;
};

const AUDIO_CONSTRAINTS: MediaTrackConstraints = {
  echoCancellation: false,
  noiseSuppression: false,
  autoGainControl: false,
};

let pending: Promise<TunerSession> | null = null;

export function armTunerAudio(): Promise<TunerSession> {
  if (!pending) {
    pending = (async () => {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: AUDIO_CONSTRAINTS,
      });
      const context = new AudioContext();
      if (context.state === "suspended") {
        await context.resume();
      }
      return { stream, context };
    })().catch((error) => {
      pending = null;
      throw error;
    });
  }
  return pending;
}

export async function stopTunerAudio(): Promise<void> {
  const started = pending;
  pending = null;
  if (!started) return;
  try {
    const session = await started;
    session.stream.getTracks().forEach((track) => track.stop());
    if (session.context.state !== "closed") {
      await session.context.close();
    }
  } catch {
    // Permission denied or already torn down.
  }
}
