import { isExpired, localDay, type Pact, type Tier } from "./api";
import { keptToday, pactDays } from "./pact-progress";

export const directions = [
  { id: "body", name: "Тело", glyph: "身", color: "#86d3a4", angle: -90, description: "Движение, здоровье и восстановление." },
  { id: "social", name: "Социум", glyph: "縁", color: "#e2c578", angle: -150, description: "Отношения, общение и внимание к людям." },
  { id: "discipline", name: "Дисциплина", glyph: "律", color: "#d0d5df", angle: 150, description: "Привычки, порядок и последовательность." },
  { id: "mind", name: "Разум", glyph: "知", color: "#c2a0ec", angle: -30, description: "Знания, обучение и работа с вниманием." },
  { id: "creation", name: "Созидание", glyph: "創", color: "#e88c9c", angle: 30, description: "Творчество, проекты и собственные результаты." },
  { id: "other", name: "Другое", glyph: "他", color: "#8fbcec", angle: 90, description: "Личные практики за пределами остальных направлений." },
] as const;
export type DirectionName = typeof directions[number]["name"];
export const tierOrder: Tier[] = ["common", "rare", "epic", "legendary"];
export type Capacity = { limit: null; counts: Record<DirectionName, Record<Tier, number>> };
const aliases: Record<string, DirectionName> = { "Осознанность": "Дисциплина", "Развитие": "Разум", "Движение": "Тело", "Фокус": "Дисциплина", "Здоровье": "Тело", "Творчество": "Созидание", "Принципы": "Социум", "Личное": "Другое" };
export function directionOf(pact: Pact): DirectionName {
  return directions.find(direction => direction.name === pact.category)?.name ?? aliases[pact.category ?? ""] ?? (pact.is_joint ? "Социум" : "Другое");
}
export function dailyEligible(pact: Pact, day = localDay()) {
  return pact.status === "active" && !isExpired(pact) && (pact.tracking_mode === "automatic" || pact.checkins.includes(day) || !pact.duration_days || pactDays(pact) < pact.duration_days);
}
export function directionSummary(pacts: Pact[], category: DirectionName, day = localDay()) {
  const active = pacts.filter(pact => pact.status === "active" && directionOf(pact) === category).sort((a, b) => a.id - b.id);
  const eligible = active.filter(pact => dailyEligible(pact, day));
  const checked = eligible.filter(pact => keptToday(pact, day)).length;
  return { active, eligible: eligible.length, checked, todayProgress: eligible.length ? Math.round(checked / eligible.length * 100) : 0,
    counts: Object.fromEntries(tierOrder.map(tier => [tier, active.filter(pact => pact.rarity === tier).length])) as Record<Tier, number> };
}
export function directionPoint(angle: number, radius = 214) {
  const radians = angle * Math.PI / 180;
  return { x: 320 + radius * Math.cos(radians), y: 320 + radius * Math.sin(radians) };
}
