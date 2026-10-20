export type AudioPreferences = { volume: number; muted: boolean; loop: boolean };
export const AUDIO_PREFERENCES_KEY = "nen:audio-preferences";
export const DEFAULT_AUDIO_PREFERENCES: AudioPreferences = { volume: 1, muted: false, loop: false };
const CHANGE_EVENT = "nen:audio-preferences-changed";
let snapshot = DEFAULT_AUDIO_PREFERENCES;
let lastRaw: string | null | undefined;

export function parseAudioPreferences(raw: string | null): AudioPreferences {
  try {
    const value = JSON.parse(raw ?? "null") as Partial<AudioPreferences> | null;
    return {
      volume: typeof value?.volume === "number" && Number.isFinite(value.volume) ? Math.max(0, Math.min(1, value.volume)) : 1,
      muted: value?.muted === true, loop: value?.loop === true,
    };
  } catch { return DEFAULT_AUDIO_PREFERENCES; }
}
export function getAudioPreferences() {
  try {
    const raw = localStorage.getItem(AUDIO_PREFERENCES_KEY);
    if (raw !== lastRaw) { lastRaw = raw; snapshot = parseAudioPreferences(raw); }
  } catch {}
  return snapshot;
}
export function serverAudioPreferences() { return DEFAULT_AUDIO_PREFERENCES; }
export function subscribeAudioPreferences(listener: () => void) {
  function storage(event: StorageEvent) { if (event.key === AUDIO_PREFERENCES_KEY || event.key === null) listener(); }
  window.addEventListener(CHANGE_EVENT, listener);
  window.addEventListener("storage", storage);
  return () => { window.removeEventListener(CHANGE_EVENT, listener); window.removeEventListener("storage", storage); };
}
export function setAudioPreferences(patch: Partial<AudioPreferences>) {
  const current = getAudioPreferences(), next = parseAudioPreferences(JSON.stringify({ ...current, ...patch }));
  if (next.volume === current.volume && next.muted === current.muted && next.loop === current.loop) return;
  snapshot = next;
  try { const raw = JSON.stringify(next); localStorage.setItem(AUDIO_PREFERENCES_KEY, raw); lastRaw = raw; } catch {}
  if (typeof window !== "undefined") window.dispatchEvent(new Event(CHANGE_EVENT));
}
