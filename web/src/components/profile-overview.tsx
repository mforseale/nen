"use client";

import Link from "next/link";
import { useState } from "react";
import type { Pact } from "@/lib/api";
import { goalPercent, type ProfileData } from "@/lib/community";
import { directions,directionPoint,directionSummary,type DirectionName } from "@/lib/directions";
import { Achievements } from "./achievement-gallery";
import { GoalEditor } from "./profile-editors";
import { PinnedFiles } from "./profile-files";
import { Avatar,YearGoals } from "./profile-sections";
import type { ProfileTab } from "./profile-tabs";
import { Icon,Modal } from "./ui";

function GoalShowcase({data,owner}:{data:ProfileData;owner:boolean}) {
  const [open,setOpen]=useState(false);const [create,setCreate]=useState(false);const year=new Date().getFullYear();const goals=data.goals.filter(goal=>goal.year === year);
  return <section className="profile-showcase overview-goals"><div className="showcase-heading"><button onClick={()=>setOpen(true)}><Icon name="target"/><h2>Цели на {year}</h2><span>{goals.filter(goal=>goal.current>=goal.target).length}/{goals.length}</span><Icon name="chevron"/></button>{owner && <button className="icon-button" onClick={()=>setCreate(true)} aria-label="Добавить цель на год"><Icon name="plus"/></button>}</div>
    {goals.length ? <div className="goal-preview-list">{goals.slice(0,3).map(goal=><button key={goal.id} onClick={()=>setOpen(true)}><span className="goal-preview-title">{goal.current>=goal.target ? <Icon name="check"/> : <Icon name="target"/>}<strong>{goal.title}</strong><b>{goalPercent(goal)}%</b></span><span className="goal-preview-progress"><i style={{width:goalPercent(goal)+"%"}}/></span><small>{goal.current} / {goal.target} {goal.unit}</small></button>)}</div> : <p className="showcase-empty">{owner ? "Обозначь, чего хочешь достичь в этом году." : "Нет доступных целей на этот год."}</p>}
    <button className="showcase-more" onClick={()=>setOpen(true)}>{goals.length>3 ? `Все цели (${goals.length})` : "Подробности и другие годы"}<Icon name="arrow"/></button>
    {open && <Modal title="Цели на год" onClose={()=>setOpen(false)} className="profile-detail-dialog"><YearGoals goals={data.goals} owner={owner}/></Modal>}{create && <GoalEditor year={year} onClose={()=>setCreate(false)}/>}
  </section>;
}

function PactPreview({pacts,onOpen}:{pacts:Pact[];onOpen:(category?:DirectionName)=>void}) {
  const summaries=directions.map(direction=>({...direction,...directionSummary(pacts,direction.name)}));
  const total=summaries.reduce((count,direction)=>count+direction.eligible,0);const checked=summaries.reduce((count,direction)=>count+direction.checked,0);
  return <section className="profile-showcase"><div className="showcase-heading"><button onClick={()=>onOpen()}><Icon name="seal"/><h2>Карта пактов</h2><span>{total ? `${checked}/${total} сегодня` : `${pacts.filter(pact=>pact.status === "active").length} активных`}</span><Icon name="chevron"/></button></div><div className="pact-preview-body"><button className="pact-mini-art" onClick={()=>onOpen()} aria-label="Открыть карту пактов"><svg viewBox="0 0 640 640" fill="none" aria-hidden="true"><polygon points={[0,3,4,5,2,1].map(index=>{const p=directionPoint(directions[index].angle);return `${p.x},${p.y}`;}).join(" ")}/>{directions.map(direction=>{const p=directionPoint(direction.angle);return <g key={direction.id}><circle cx={p.x} cy={p.y} r="40" stroke={direction.color}/><text x={p.x} y={p.y+16} fill={direction.color}>{direction.glyph}</text></g>;})}<text className="mini-nen" x="320" y="360">念</text></svg></button><div className="direction-preview-grid">{summaries.map(direction=><button key={direction.id} onClick={()=>onOpen(direction.name)}><i style={{background:direction.color}}/><strong>{direction.name}</strong><span>{direction.checked}/{direction.eligible}</span></button>)}</div></div></section>;
}

function FriendsShowcase({data,owner}:{data:ProfileData;owner:boolean}) {
  return <section className="profile-showcase"><div className="showcase-heading">{owner ? <Link href="/friends"><Icon name="friends"/><h2>Друзья</h2><span>{data.friend_count}</span><Icon name="chevron"/></Link> : <div><Icon name="friends"/><h2>Друзья</h2><span>{data.friend_count}</span></div>}</div>{data.friend_preview?.length ? <div className="friend-avatar-preview">{data.friend_preview.map(person=><Link key={person.id} href={"/people/"+person.username} title={person.full_name} aria-label={"Профиль: "+person.full_name}><Avatar person={person}/></Link>)}</div> : <p className="showcase-empty">{owner ? "Добавляй друзей через поиск пользователей." : "Друзей пока нет."}</p>}</section>;
}

export function ProfileOverview({data,owner=false,pacts=[],onNavigate,onDirection}:{data:ProfileData;owner?:boolean;pacts?:Pact[];onNavigate:(tab:ProfileTab)=>void;onDirection?:(category?:DirectionName)=>void}) {
  return <div className="profile-overview-grid"><div className="overview-main"><GoalShowcase data={data} owner={owner}/>{owner && onDirection ? <PactPreview pacts={pacts} onOpen={onDirection}/> : <section className="profile-showcase"><div className="showcase-heading"><button onClick={()=>onNavigate("feed")}><Icon name="message"/><h2>Лента</h2><span>{data.posts.length} постов</span><Icon name="chevron"/></button></div><p className="showcase-empty">Записи и вложения, которыми делится {data.user.full_name}.</p></section>}</div><aside className="overview-side"><FriendsShowcase data={data} owner={owner}/><PinnedFiles files={data.pins ?? []} owner={owner} compact/></aside><div className="overview-wide"><Achievements items={data.achievements} compact onViewAll={()=>onNavigate("achievements")}/></div></div>;
}
