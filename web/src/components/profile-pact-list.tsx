"use client";
import Link from "next/link";
import { useState } from "react";
import { api,formatDate,isExpired,refreshData,tiers,type Pact } from "@/lib/api";
import { pactDays, pactStreak } from "@/lib/pact-progress";
import { directionOf } from "@/lib/directions";
import { Action,Icon } from "./ui";
import { PactBreakAction } from "./pact-streak";

export function ProfilePactList({pacts}:{pacts:Pact[]}) {
  const [history,setHistory]=useState(false);
  const active=pacts.filter(pact=>pact.status === "active");const past=pacts.filter(pact=>pact.status!=="active" && pact.status!=="draft");const visible=history ? past : active;
  return <details className="profile-pact-details"><summary><Icon name="list"/><strong>Мои пакты / История</strong><span>{active.length} активных · {past.length} в истории</span><Icon name="chevron"/></summary><div className="pact-details-body"><div className="plain-tabs"><button className={!history ? "active" : ""} onClick={()=>setHistory(false)}>Мои пакты <span>{active.length}</span></button><button className={history ? "active" : ""} onClick={()=>setHistory(true)}>История <span>{past.length}</span></button></div><div className="compact-pact-list">{visible.map(pact=><article key={pact.id}><div><div className="compact-pact-meta"><span className={"tier tier-"+pact.rarity}>{tiers[pact.rarity].label}</span><span>{directionOf(pact)}</span>{pact.is_joint && <Icon name="friends" size={24}/>}</div><h3>{pact.title}</h3><p>{pactDays(pact)}{pact.duration_days ? ` / ${pact.duration_days}` : ""} дней соблюдения · серия {pactStreak(pact)} дн.{pact.deadline && " · до "+formatDate(pact.deadline)}</p></div><div className="compact-pact-actions"><strong>{pact.progress === null ? "∞" : pact.progress+"%"}</strong>{pact.status!=="active" ? <span>{pact.status === "completed" ? "Завершён" : pact.status === "failed" ? "Не выполнен" : "Отменён"}</span> : isExpired(pact) ? pact.can_manage ? <Action onClick={async()=>{await api(`/my/pacts/${pact.id}/complete`,"POST");refreshData();}}>Завершить</Action> : <span>Срок истёк</span> : <PactBreakAction pact={pact} compact/>}{pact.is_joint && <Link href={"/forum?pact="+pact.id} className="text-link">Обсуждение</Link>}</div></article>)}</div>{!visible.length && <p className="showcase-empty">{history ? "История пактов пуста." : "Нет активных пактов."}</p>}</div></details>;
}
