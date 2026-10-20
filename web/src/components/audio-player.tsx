"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";
import { getAudioPreferences, serverAudioPreferences, setAudioPreferences, subscribeAudioPreferences } from "@/lib/audio-preferences";
import { Icon } from "./ui";

export function AudioPlayer({ src, label = "Музыка" }: { src: string; label?: string }) {
  const audio = useRef<HTMLAudioElement>(null);
  const preferences = useSyncExternalStore(subscribeAudioPreferences, getAudioPreferences, serverAudioPreferences);
  useEffect(() => {
    if (!audio.current) return;
    audio.current.volume = preferences.volume;
    audio.current.muted = preferences.muted;
  }, [preferences.volume, preferences.muted, src]);
  return <div className="nen-audio-player" role="group" aria-label={label}>
    <audio ref={audio} controls preload="none" src={src} loop={preferences.loop} aria-label={label} onVolumeChange={event => setAudioPreferences({ volume: event.currentTarget.volume, muted: event.currentTarget.muted })}/>
    <div className="audio-preference-controls">
      <button type="button" className="audio-repeat" aria-pressed={preferences.loop} aria-label="Повторять трек бесконечно" onClick={() => setAudioPreferences({ loop: !preferences.loop })}><Icon name="repeat" size={20}/><span>Повтор</span></button>
      <label className="audio-volume"><Icon name="volume" size={20}/><span className="sr-only">Громкость</span><input type="range" min={0} max={100} step={1} value={Math.round(preferences.volume * 100)} aria-label="Громкость" onChange={event => setAudioPreferences({ volume: Number(event.target.value) / 100, muted: false })}/><output>{Math.round(preferences.volume * 100)}%</output></label>
    </div>
  </div>;
}
