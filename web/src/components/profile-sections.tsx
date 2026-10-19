"use client";
/* eslint-disable @next/next/no-img-element -- Private image requests must carry the browser session and recheck visibility. */

import Link from "next/link";
import { useState } from "react";
import { api, refreshData, type Person } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { profileHref } from "@/lib/profile-navigation";
import { audiences, goalPercent, type Relationship, type YearGoal } from "@/lib/community";
import { GoalEditor } from "./profile-editors";
import { Action, Icon, Modal } from "./ui";

export function Avatar({ person, large = false }: { person: Person; large?: boolean }) {
  return <span className={"person-avatar " + (large ? "large" : "")}>{person.avatar_url ? <img src={person.avatar_url} alt={"Аватар: " + person.full_name}/> : <span aria-hidden="true">{person.full_name.slice(0, 1).toUpperCase()}</span>}</span>;
}

export function FriendControls({ username, relationship }: { username: string; relationship: Relationship }) {
  const { user } = useAuth();
  const { status, id } = relationship;
  if (status === "self") return <Link className="button" href={profileHref(username)}>Мой профиль <Icon name="arrow" size={16}/></Link>;
  if (!user) return <Link className="button" href="/login">Добавить в друзья <Icon name="friends" size={16}/></Link>;
  return <div className="friend-controls">
    {status === "none" && <Action onClick={async () => {await api("/friends", "POST", { username });refreshData();}}>Добавить в друзья <Icon name="friends" size={16}/></Action>}
    {status === "outgoing" && <><span className="muted">Заявка отправлена</span><Action className="button-quiet" onClick={async () => {await api(`/friends/${id}`, "DELETE");refreshData();}}>Отменить заявку</Action></>}
    {status === "incoming" && <><Action className="button-red" onClick={async () => {await api(`/friends/${id}/respond`, "POST", { accept: true });refreshData();}}>Принять в друзья <Icon name="check" size={16}/></Action><Action className="button-quiet" onClick={async () => {await api(`/friends/${id}/respond`, "POST", { accept: false });refreshData();}}>Отклонить</Action></>}
    {status === "friends" && <><span className="friend-status"><Icon name="friends" size={17}/>Вы друзья</span><Action className="button-quiet" onClick={async () => {await api(`/friends/${id}`, "DELETE");refreshData();}}>Убрать из друзей</Action></>}
  </div>;
}

export function YearGoals({ goals, owner = false }: { goals: YearGoal[]; owner?: boolean }) {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(currentYear); const [editing, setEditing] = useState<YearGoal | "new" | null>(null); const [removing, setRemoving] = useState<YearGoal | null>(null);
  const years = Array.from(new Set([currentYear - 1, currentYear, currentYear + 1, ...goals.map(goal => goal.year)])).sort((a, b) => b - a);
  const items = goals.filter(goal => goal.year === year);
  return <section className="profile-module" aria-labelledby="year-goals-title">
    <div className="module-heading"><div><h2 id="year-goals-title"><Icon name="target"/>Цели на год</h2><p>{items.filter(goal => goal.current >= goal.target).length} из {items.length} выполнено за {year} год</p></div><div className="module-actions"><label className="year-select"><span className="sr-only">Год целей</span><select value={year} onChange={event => setYear(Number(event.target.value))}>{years.map(value => <option key={value}>{value}</option>)}</select></label>{owner && <button className="button" onClick={() => setEditing("new")}><Icon name="plus" size={16}/>Добавить цель</button>}</div></div>
    {items.length ? <div className="year-goals-list">{items.map(goal => <article key={goal.id} className={"year-goal " + (goal.current >= goal.target ? "complete" : "")}>
      <span className="goal-status"><Icon name={goal.current >= goal.target ? "check" : "target"} size={21}/></span><div className="goal-content"><div className="goal-topline"><h3>{goal.title}</h3><span className="audience-label"><Icon name={goal.visibility === "public" ? "globe" : goal.visibility === "friends" ? "friends" : "lock"} size={13}/>{audiences[goal.visibility]}</span></div>{goal.description && <p>{goal.description}</p>}<div className="goal-progress-caption"><strong>{goal.current} / {goal.target} {goal.unit}</strong><span>{goalPercent(goal)}%</span></div><div className="goal-progress-track" role="progressbar" aria-label={goal.title} aria-valuemin={0} aria-valuemax={goal.target} aria-valuenow={goal.current}><span style={{width: goalPercent(goal) + "%"}}/></div></div>
      {owner && <div className="goal-actions"><Action className="button-quiet" disabled={goal.current >= goal.target} onClick={async () => {await api(`/my/goals/${goal.id}`, "PUT", {...goal, current: goal.current + 1});refreshData();}}>+1</Action><button className="icon-button" aria-label={"Изменить цель «" + goal.title + "»"} onClick={() => setEditing(goal)}><Icon name="settings" size={17}/></button><button className="icon-button" aria-label={"Удалить цель «" + goal.title + "»"} onClick={() => setRemoving(goal)}><Icon name="trash" size={17}/></button></div>}
    </article>)}</div> : <div className="profile-empty-line"><Icon name="target" size={22}/><p>{owner ? "Добавь то, чего хочешь достичь за этот год. Для каждой цели можно указать измеримый результат." : "На этот год нет доступных целей."}</p></div>}
    {editing && <GoalEditor goal={editing === "new" ? undefined : editing} year={year} onSaved={setYear} onClose={() => setEditing(null)}/>}
    {removing && <Modal title="Удалить цель?" onClose={() => setRemoving(null)}><p className="detail-description">{removing.title}</p><p className="muted">Цель и её прогресс будут удалены.</p><Action className="button-red full-width" onClick={async () => {await api(`/my/goals/${removing.id}`, "DELETE");setRemoving(null);refreshData();}}>Удалить цель <Icon name="trash" size={16}/></Action></Modal>}
  </section>;
}


export { Achievements } from "./achievement-gallery";
export { ProfilePosts } from "./profile-feed";
