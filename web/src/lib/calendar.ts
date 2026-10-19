import type { Entry } from "./api";

export type PlannerView = "month" | "week" | "agenda";
export const calendarColors = ["#df6b79", "#e4b563", "#88be85", "#79b8e0", "#b596e0", "#df956b", "#d589af", "#70b9aa", "#bdc777", "#91a5df"];
export const calendarThemes = [
  { id: "classic", label: "Классический", description: "Чёткие панели и цветные метки", icon: "calendar" },
  { id: "grid", label: "Сетка", description: "Выразительная сетка и акцентные дни", icon: "grid" },
  { id: "journal", label: "Ежедневник", description: "Тёплый фон, линейки и книжный шрифт", icon: "feather" },
] as const;
export const entryKinds = {
  task: { label: "Задача", icon: "check" },
  event: { label: "Событие", icon: "calendar" },
  note: { label: "Заметка", icon: "feather" },
} as const;

export function dayKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
export function parseDay(day: string) { return new Date(day + "T12:00:00"); }
export function addDays(date: Date, days: number) { const next = new Date(date); next.setDate(next.getDate() + days); return next; }
export function periodFor(anchor: Date, view: PlannerView) {
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1, 12);
  if (view === "agenda") return { start: first, end: new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0, 12) };
  const start = view === "week" ? new Date(anchor) : first;
  start.setDate(start.getDate() - (start.getDay() + 6) % 7);
  return { start, end: addDays(start, view === "week" ? 6 : 41) };
}
export function longDay(day: string) {
  return parseDay(day).toLocaleDateString("ru-RU", { weekday: "long", day: "numeric", month: "long" });
}
export function sortEntries(items: Entry[]) {
  const priority = { high: 0, normal: 1, low: 2 };
  return [...items].sort((a, b) => a.day.localeCompare(b.day) || Number(a.completed) - Number(b.completed) || (a.start_time ?? "00:00").localeCompare(b.start_time ?? "00:00") || priority[a.priority] - priority[b.priority] || a.id - b.id);
}
export function isOverdue(entry: Entry, now = new Date()) {
  return entry.kind === "task" && !entry.completed && (entry.day < dayKey(now) || (entry.day === dayKey(now) && !!entry.start_time && entry.start_time < `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`));
}
