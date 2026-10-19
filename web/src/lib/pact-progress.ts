import type { Pact } from "./api";

/** Automatic totals are server projections; legacy checkins remain as history. */
export function pactDays(pact: Pact) { return pact.total_days ?? pact.checkins.length; }
export function pactStreak(pact: Pact) { return pact.streak_days ?? 0; }
export function brokenToday(pact: Pact, day: string) {
  return pact.last_break_on === day || !!pact.broken_days?.includes(day);
}
export function keptToday(pact: Pact, day: string) {
  return pact.tracking_mode === "automatic" ? !brokenToday(pact, day) : pact.checkins.includes(day);
}
