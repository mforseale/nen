"use client";

import { useCallback, useEffect, useState } from "react";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "/api/v1";
export type Person = { id: number; username: string; full_name: string; avatar_url?: string | null };
export type Tier = "common" | "rare" | "epic" | "legendary";
export type Pact = { id: number; title: string; description: string; rarity: Tier; status: string; is_joint: boolean; is_custom?: boolean; can_manage?: boolean; category?: string; template_id: string | null; duration_days: number | null; deadline: string | null; created_at: string; progress: number | null; checkins: string[]; members: Person[] };
export type Note = { id: number; title: string; content: string; visibility: "public" | "invited" | "private"; author: Person; invitees: string[]; created_at: string; updated_at: string };
export type PactRequest = { id: number; pact_id: number; title: string; description: string; duration_days: number; category: string; rarity: Tier; incoming: boolean; sender: Person; recipient: Person; status: string; created_at: string };
export type ForumTopic = { template_id: string | null; pact_id: number | null; title: string };
export type Comment = { id: number; content: string; template_id: string | null; pact_id: number | null; topic_title: string; author: Person; created_at: string };
export type Forum = { comments: Comment[]; topics: ForumTopic[]; trending: (ForumTopic & {count: number})[] };
export type CalendarTheme = "classic" | "grid" | "journal";
export type Calendar = { id: number; name: string; color: string; theme: CalendarTheme };
export type EntryKind = "task" | "event" | "note";
export type Entry = { id: number; calendar_id: number; title: string; day: string; kind: EntryKind; description: string; start_time: string | null; end_time: string | null; priority: "low" | "normal" | "high"; completed: boolean };
export const tiers: Record<Tier, { label: string; duration: string; numeral: string }> = {
  common: { label: "Common", duration: "7 дней", numeral: "I" },
  rare: { label: "Rare", duration: "1 месяц", numeral: "II" },
  epic: { label: "Epic", duration: "1 год", numeral: "III" },
  legendary: { label: "Legendary", duration: "Всю жизнь", numeral: "IV" },
};

export async function api<T>(path: string, method = "GET", body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(API_URL + path, { method, credentials: "include", signal, headers: body === undefined ? undefined : { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    const detail = typeof error.detail === "string" ? error.detail : response.status === 401 ? "Войдите в профиль, чтобы продолжить." : response.status === 422 ? "Проверьте заполненные поля." : `Не удалось выполнить запрос (${response.status}).`;
    throw new Error(detail);
  }
  return response.status === 204 ? undefined as T : response.json();
}

export function refreshData() { window.dispatchEvent(new Event("nen:refresh")); }
export function useApi<T>(path: string | null) {
  const [state, setState] = useState<{ path: string | null; data: T | null; error: string | null; loading: boolean }>({ path: null, data: null, error: null, loading: true });
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision(v => v + 1), []);
  useEffect(() => { window.addEventListener("nen:refresh", reload); return () => window.removeEventListener("nen:refresh", reload); }, [reload]);
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    api<T>(path, "GET", undefined, controller.signal).then(data => setState({ path, data, error: null, loading: false })).catch(error => {
      if (!controller.signal.aborted) setState({ path, data: null, error: error instanceof TypeError ? "Сервер недоступен. Проверьте, что API запущен." : error.message, loading: false });
    });
    return () => controller.abort();
  }, [path, revision]);
  return { data: state.path === path ? state.data : null, error: state.path === path ? state.error : null, loading: path !== null && (state.path !== path || state.loading), reload };
}

export function localDay(date = new Date()) { return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`; }
export function checkinPayload() { return { day: localDay(), utc_offset_minutes: -new Date().getTimezoneOffset() }; }
export function isExpired(pact: Pact) { return !!pact.deadline && new Date(pact.deadline.endsWith("Z") || /[+]\d\d:\d\d$/.test(pact.deadline) ? pact.deadline : pact.deadline+"Z").getTime() <= Date.now(); }
export function formatDate(value: string) { return new Date(value.endsWith("Z") || /[+]\d\d:\d\d$/.test(value) ? value : value + (value.includes("T") ? "Z" : "T12:00:00")).toLocaleDateString("ru-RU", { day: "numeric", month: "long" }); }
