"use client";

import Link from "next/link";
import { useId, useRef, useState, type CSSProperties, type FormEvent, type KeyboardEvent } from "react";
import { api, checkinPayload, formatDate, isExpired, localDay, refreshData, tiers, type Pact, type Tier } from "@/lib/api";
import { directionOf, directionPoint, directions, directionSummary, tierOrder, type DirectionName } from "@/lib/directions";
import { Action, ErrorMessage, Icon, Modal } from "./ui";

function ManagePact({ pact }: { pact: Pact }) {
  const [mode, setMode] = useState<"move" | "cancel" | null>(null);
  const [error, setError] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  if (!pact.can_manage) return null;
  async function move(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const category = new FormData(event.currentTarget).get("category");setBusy(true);setError(null);
    try {await api(`/my/pacts/${pact.id}/category`, "PUT", {category});setMode(null);refreshData();}
    catch(error) {setError((error as Error).message);} finally {setBusy(false);}
  }
  return <><div className="hex-manage"><button onClick={() => {setMode("move");setError(null);}}>Перенести <Icon name="arrow" size={18}/></button><button onClick={() => setMode("cancel")}>Отменить пакт</button></div>
    {mode === "move" && <Modal title="Перенести пакт" onClose={() => setMode(null)}><form className="form-stack" onSubmit={move}><p className="muted">{pact.title}. Даты, условия и отметки сохранятся.</p><label>Направление<select name="category" defaultValue={directionOf(pact)}>{directions.map(direction => <option key={direction.id}>{direction.name}</option>)}</select></label><p className="form-caption">Нужно свободное место для {tiers[pact.rarity].label}. У совместного пакта — у обоих участников.</p><ErrorMessage error={error}/><button className="button button-red" disabled={busy}>{busy ? "Переносим…" : "Перенести пакт"}</button></form></Modal>}
    {mode === "cancel" && <Modal title="Отменить пакт?" onClose={() => setMode(null)}><p className="detail-description">{pact.title}</p><p className="muted">Пакт перейдёт в историю, а место освободится. Отметки сохранятся.{pact.is_joint && " Совместный пакт завершит действие для обоих участников."}</p><Action className="button-red full-width" onClick={async () => {await api(`/my/pacts/${pact.id}/cancel`, "POST");setMode(null);refreshData();}}>Отменить пакт</Action></Modal>}
  </>;
}

export function PactSeal({ pacts: records, onCreate, initialCategory = null, initialPactId = null }: { pacts: Pact[]; initialCategory?: DirectionName | null; initialPactId?: number | null; onCreate?: (category: DirectionName, tier: Tier) => void }) {
  const active = records.filter(pact => pact.status === "active");
  const target = active.find(pact => pact.id === initialPactId);
  const [chosen, setChosen] = useState<DirectionName | null>(target ? directionOf(target) : initialCategory);
  const [chosenTier, setTier] = useState<Tier | null>(target?.rarity ?? null); const [selectedId, setSelectedId] = useState<number | null>(target?.id ?? null);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]); const panelId = useId();
  const category = chosen ?? directions.find(direction => active.some(pact => directionOf(pact) === direction.name))?.name ?? "Тело";
  const direction = directions.find(item => item.name === category)!;
  const summary = directionSummary(active, category);
  const tier = chosenTier ?? tierOrder.find(value => summary.counts[value] > 0) ?? "common";
  const pacts = summary.active.filter(pact => pact.rarity === tier);
  const selected = pacts.find(pact => pact.id === selectedId) ?? pacts[0];
  const today = localDay(); const eligible = directions.reduce((total, item) => total + directionSummary(active, item.name, today).eligible, 0);
  const done = directions.reduce((total, item) => total + directionSummary(active, item.name, today).checked, 0);
  function choose(name: DirectionName) {setChosen(name);setTier(null);setSelectedId(null);}
  function keyboard(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const order = [0, 3, 4, 5, 2, 1]; const current = order.indexOf(index);
    let next: number;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = order[(current + 1) % 6];
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = order[(current + 5) % 6];
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = 5;
    else return;
    event.preventDefault();buttons.current[next]?.focus();
  }
  return <section className="hex-section" aria-label="Карта пактов по шести направлениям">
    <div className="hex-heading"><div><h2>Карта пактов</h2><p>Шесть направлений. В каждом — до трёх активных пактов одного тира.</p></div><span>{active.length} / 72 <small>активных пактов</small></span></div>
    <div className="hex-layout">
      <div className="hex-visual"><div className="hex-art">
        <svg className="hex-lines" viewBox="0 0 640 640" fill="none" aria-hidden="true"><polygon points={[0,3,4,5,2,1].map(index => {const point=directionPoint(directions[index].angle);return `${point.x},${point.y}`;}).join(" ")}/>{directions.map(item => {const point = directionPoint(item.angle);return <path key={item.id} d={`M320 320 ${point.x} ${point.y}`}/>;})}</svg>
        <div className="hex-core"><span lang="ja" aria-hidden="true">念</span>{eligible > 0 ? <><strong>{done}<i>/</i>{eligible}</strong><small>сегодня</small></> : <small>{active.length ? "нет отметок на сегодня" : "нет пактов"}</small>}</div>
        {directions.map((item, index) => {
          const point = directionPoint(item.angle); const stats = directionSummary(active, item.name, today);
          return <button key={item.id} ref={element => {buttons.current[index] = element;}} className={"hex-node " + (item.name === category ? "selected" : "")} data-direction={item.id} data-angle={item.angle} aria-label={`${item.name}: ${stats.active.length} активных пактов. Сегодня ${stats.checked} из ${stats.eligible}`} aria-pressed={item.name === category} aria-controls={panelId} style={{left:point.x/640*100+"%",top:point.y/640*100+"%","--direction-color":item.color} as CSSProperties} onClick={() => choose(item.name)} onFocus={() => {if(chosen !== item.name) choose(item.name);}} onKeyDown={event => keyboard(event,index)}>
            <span className="hex-node-symbol"><svg viewBox="0 0 84 84" fill="none" aria-hidden="true"><circle className="hex-node-track" cx="42" cy="42" r="37"/>{stats.eligible > 0 && <circle className="hex-node-progress" data-today-progress={stats.todayProgress} cx="42" cy="42" r="37" pathLength="100" strokeDasharray={`${stats.todayProgress} 100`} transform="rotate(-90 42 42)"/>}</svg><span lang="ja" aria-hidden="true">{item.glyph}</span></span>
            <strong>{item.name}</strong><small>{stats.active.length} пактов{stats.eligible > 0 && <b> · {stats.checked}/{stats.eligible} ✓</b>}</small>
          </button>;
        })}
      </div><p className="hex-explanation"><Icon name="check" size={19}/>Цветной контур — выполнение сегодня. Нажми на направление.</p></div>
      <div className="hex-panel" id={panelId} style={{"--direction-color":direction.color} as CSSProperties}>
        <header className="hex-panel-heading"><div><p>НАПРАВЛЕНИЕ</p><h3>{direction.name}</h3></div><span>{summary.active.length}<small>/12</small></span></header><p className="hex-panel-description">{direction.description}</p>
        <p className="hex-panel-daily"><Icon name="check" size={22}/>{summary.eligible ? <>Сегодня <strong>{summary.checked} из {summary.eligible}</strong></> : "На сегодня нет доступных отметок"}</p>
        <div className="hex-tier-tabs" aria-label={"Тиры направления «" + category + "»"}>{tierOrder.map(value => <button key={value} data-tier={value} className={tier === value ? "active" : ""} aria-pressed={tier === value} onClick={() => {setTier(value);setSelectedId(null);}}><span className={"tier tier-"+value}>{tiers[value].label}</span><strong>{summary.counts[value]}<small>/3</small></strong><span className="hex-slot-marks" aria-hidden="true">{[0,1,2].map(index => <i key={index} className={index < summary.counts[value] ? "occupied" : ""}/>)}</span></button>)}</div>
        {pacts.length > 3 && <p className="hex-overflow" role="status">Сохранены все {pacts.length} пакта из прежней версии. Лимит — 3: перенеси, заверши или отмени лишние, чтобы освободить место.</p>}
        <div className="hex-pact-slots" aria-label={`${category}, ${tiers[tier].label}: ${pacts.length} из 3 мест занято`}>
          {pacts.map((pact,index) => <button key={pact.id} className={"hex-pact-slot " + (selected?.id === pact.id ? "selected" : "")} data-pact-id={pact.id} aria-pressed={selected?.id === pact.id} onClick={() => setSelectedId(pact.id)}><span className="hex-slot-number">{String(index+1).padStart(2,"0")}</span><span><strong>{pact.title}</strong><small>{pact.is_joint ? "Совместный" : "Личный пакт"}{isExpired(pact) ? " · срок истёк" : pact.checkins.includes(today) ? " · сегодня отмечено" : ""}</small></span><b>{pact.checkins.includes(today) ? <Icon name="check" size={21}/> : pact.progress === null ? "∞" : pact.progress + "%"}</b></button>)}
          {Array.from({length:Math.max(0,3-pacts.length)},(_,index) => <button key={"empty"+index} data-free-slot className="hex-pact-slot empty" disabled={!onCreate} onClick={() => onCreate?.(category,tier)}><span className="hex-slot-number">{String(pacts.length+index+1).padStart(2,"0")}</span><span><strong>Свободно</strong><small>Добавить {tiers[tier].label}</small></span><Icon name="plus" size={22}/></button>)}
        </div>
        {selected ? <div className="hex-pact-detail" key={selected.id}>
          <div className="hex-detail-meta"><span className={"tier tier-"+selected.rarity}>{tiers[selected.rarity].label}</span>{selected.is_joint && <span><Icon name="link" size={17}/>Совместный пакт</span>}</div><h4>{selected.title}</h4><p className="hex-conditions">{selected.description}</p>
          <div className="hex-progress-summary"><strong>{selected.progress === null ? "∞" : selected.progress + "%"}</strong><span>{selected.duration_days ? `${selected.checkins.length} из ${selected.duration_days} дней с отметками` : `Дней с отметками: ${selected.checkins.length}`}</span></div>
          {selected.progress !== null && <div className="hex-pact-progress" role="progressbar" aria-label={"Прогресс: "+selected.title} aria-valuemin={0} aria-valuemax={100} aria-valuenow={selected.progress}><span style={{width:Math.max(0,Math.min(100,selected.progress))+"%"}}/></div>}
          <div className="hex-deadline"><Icon name="calendar" size={18}/>{selected.deadline ? "До "+formatDate(selected.deadline) : "Без конечной даты"}</div>
          {isExpired(selected) ? selected.can_manage ? <Action className="full-width" onClick={async () => {await api(`/my/pacts/${selected.id}/complete`,"POST");refreshData();}}>Завершить пакт <Icon name="check"/></Action> : <p className="muted">Срок истёк. Завершить совместный пакт может автор.</p> : <Action className="button-red full-width" disabled={selected.checkins.includes(today) || !!selected.duration_days && selected.checkins.length >= selected.duration_days} onClick={async () => {await api(`/my/pacts/${selected.id}/checkin`,"POST",checkinPayload());refreshData();}}>{selected.checkins.includes(today) ? "Сегодня отмечено" : selected.duration_days && selected.checkins.length >= selected.duration_days ? "Все дни отмечены" : "Отметить сегодня"}<Icon name="check"/></Action>}
          <Link className="hex-discussion" href={`/forum?pact=${selected.id}`}>Обсуждение <Icon name="message" size={19}/></Link>
          {selected.template_id && <Link className="hex-discussion" href={`/forum?topic=${selected.template_id}`}>Архив обсуждения <Icon name="book" size={19}/></Link>}
          <ManagePact pact={selected}/>
        </div> : <div className="hex-empty"><p>{active.length ? "В этом тире пока нет пактов. Добавь свой пакт в свободное место." : "Нет активных пактов. Выбери направление и заключи первый пакт."}</p>{onCreate ? <button className="text-link" onClick={() => onCreate(category,tier)}>Создать свой пакт <Icon name="plus"/></button> : <Link className="text-link" href={`/?category=${encodeURIComponent(category)}&tier=${tier}`}>Создать свой пакт <Icon name="arrow"/></Link>}</div>}
      </div>
    </div>
  </section>;
}
