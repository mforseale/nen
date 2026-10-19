"use client";

import { useState } from "react";
import { api, checkinPayload, formatDate, localDay, refreshData, type Pact } from "@/lib/api";
import { brokenToday, pactDays, pactStreak } from "@/lib/pact-progress";
import { Action, Icon, Modal } from "./ui";

export function StreakSummary({ pact }: { pact: Pact }) {
  return <><div className="streak-summary"><div><Icon name="flame"/><strong>{pactStreak(pact)}</strong><span>дней подряд</span></div><div><Icon name="calendar"/><strong>{pactDays(pact)}</strong><span>дней всего</span></div></div>{!!pact.broken_days?.length && <details className="streak-history"><summary>История срывов <span>{pact.broken_days.length}</span></summary><ol>{[...pact.broken_days].reverse().map(day=><li key={day}><Icon name="calendar" size={20}/><time dateTime={day}>{formatDate(day)}</time></li>)}</ol></details>}</>;
}

export function PactBreakAction({ pact, compact = false }: { pact: Pact; compact?: boolean }) {
  const [confirm, setConfirm] = useState(false);
  const broken = brokenToday(pact, localDay());
  return <><button className={compact ? "button button-quiet streak-break-button" : "button button-quiet full-width streak-break-button"} disabled={broken} onClick={() => setConfirm(true)}><Icon name={broken ? "calendar" : "flame"}/>{broken ? "Срыв отмечен сегодня" : "Отметить срыв"}</button>
    {confirm && <Modal title="Отметить срыв сегодня?" onClose={() => setConfirm(false)}><div className="streak-break-confirm"><p className="detail-description">{pact.title}</p><p>Сегодняшний день не будет засчитан. Текущая серия обнулится, а накопленные дни и история сохранятся.</p><p className="muted">Новая серия начнётся завтра автоматически.{pact.is_joint && " Это изменит только твою серию, а не прогресс другого участника."}</p><Action className="button-red full-width" onClick={async () => {await api(`/my/pacts/${pact.id}/break`, "POST", checkinPayload());setConfirm(false);refreshData();}}>Подтвердить срыв</Action><button className="button button-quiet full-width" onClick={() => setConfirm(false)}>Продолжаю пакт</button></div></Modal>}
  </>;
}
