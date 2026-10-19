"use client";

import Link from "next/link";
import { useState, type CSSProperties } from "react";
import { directions } from "@/lib/directions";
import type { Achievement } from "@/lib/community";
import { Icon, Modal } from "./ui";

const colors: Record<string,string> = {common:"#cfd3de",rare:"#8ab9f2",epic:"#c8a7ed",legendary:"#e5bf79"};
export function AchievementArt({ item }: { item: Achievement }) {
  const direction=directions.find(direction=>direction.name === item.title);
  const glyph=direction?.glyph ?? (item.tier ? {common:"I",rare:"II",epic:"III",legendary:"IV"}[item.tier] : item.id === "first-step" ? "始" : "誓");
  return <div className="achievement-art" style={{"--achievement-color":direction?.color ?? colors[item.tier ?? ""] ?? "#cf9eae"} as CSSProperties} aria-hidden="true"><svg viewBox="0 0 360 170" fill="none"><path d="M180 12 246 49v72l-66 37-66-37V49Z"/><circle cx="180" cy="85" r="63"/><path d="M0 85h99m162 0h99M180 0v12m0 146v12M55 20l50 29m150 72 50 29M55 150l50-29m150-72 50-29"/><circle cx="180" cy="85" r="78" strokeDasharray="2 9"/></svg><span lang="ja">{glyph}</span><b><Icon name={item.earned ? "check" : "lock"} size={22}/></b></div>;
}
export function Achievements({ items, compact=false, onViewAll }: { items: Achievement[]; compact?: boolean; onViewAll?: () => void }) {
  const [group,setGroup]=useState("all"); const [selected,setSelected]=useState<Achievement|null>(null);
  const filtered=items.filter(item=>group === "all" || (group === "earned" ? item.earned : item.group === group)).sort((a,b)=>Number(b.earned)-Number(a.earned));
  const visible=compact ? filtered.slice(0,4) : filtered;
  return <section className={"achievement-showcase profile-showcase "+(compact ? "compact" : "")} aria-label="Достижения">
    <div className="showcase-heading">{onViewAll ? <button onClick={onViewAll}><Icon name="award"/><h2>Достижения</h2><span>{items.filter(item=>item.earned).length} / {items.length}</span><Icon name="chevron"/></button> : <div><Icon name="award"/><h2>Достижения</h2><span>{items.filter(item=>item.earned).length} / {items.length}</span></div>}</div>
    {!compact && <><p className="achievement-intro">Открой карточку, чтобы увидеть условия и свой прогресс. Учитываются реальные отметки в пактах.</p><div className="profile-filters" aria-label="Виды достижений">{[["all","Все"],["earned","Получены"],["tier","По тирам"],["topic","По направлениям"],["path","Общие"]].map(([value,label])=><button key={value} className={group === value ? "active" : ""} aria-pressed={group === value} onClick={()=>setGroup(value)}>{label}</button>)}</div></>}
    <div className="achievement-banner-grid">{visible.map(item=><button key={item.id} data-tier={item.tier ?? undefined} className={"achievement "+(item.earned ? "earned" : "locked")} onClick={()=>setSelected(item)} aria-label={item.title+": "+(item.earned ? "получено" : `${Math.min(item.count,item.target)} из ${item.target}`)}><AchievementArt item={item}/><div className="achievement-banner-caption"><h3>{item.title}</h3><small>{item.earned ? "Получено" : "В процессе"} · {Math.min(item.count,item.target)} / {item.target}</small><span><i style={{width:Math.min(100,item.count/item.target*100)+"%"}}/></span></div></button>)}</div>
    {!visible.length && <p className="showcase-empty">Полученных достижений пока нет. Первая отметка откроет «Первый шаг».</p>}
    {selected && <Modal title={selected.title} onClose={()=>setSelected(null)} className="achievement-detail-dialog"><AchievementArt item={selected}/><p className="achievement-detail-status"><Icon name={selected.earned ? "award" : "target"}/>{selected.earned ? "Достижение получено" : "Достижение в процессе"}</p><h3 className="achievement-criteria-title">Условие</h3><p className="detail-description">{selected.description}</p><div className="achievement-detail-progress"><strong>{Math.min(selected.count,selected.target)} / {selected.target}</strong><span>{Math.min(100,Math.round(selected.count/selected.target*100))}%</span></div><div className="goal-progress-track"><span style={{width:Math.min(100,selected.count/selected.target*100)+"%"}}/></div><p className="muted">{selected.earned ? "Условия выполнены. Достижение добавлено в витрину." : `Осталось: ${Math.max(0,selected.target-selected.count)}. Активные и завершённые пакты с отметками учитываются вместе.`}</p><Link href={"/?"+new URLSearchParams({...selected.tier ? {tier:selected.tier} : {},...directions.some(direction=>direction.name === selected.title) ? {category:selected.title} : {}})} className="button">Создать свой пакт <Icon name="arrow"/></Link>{onViewAll && <button className="text-link achievement-open-all" onClick={()=>{setSelected(null);onViewAll();}}>Все достижения <Icon name="chevron"/></button>}</Modal>}
  </section>;
}
