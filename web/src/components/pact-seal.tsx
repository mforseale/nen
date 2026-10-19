"use client";

import Link from "next/link";
import { useId, useRef, useState, type CSSProperties, type FormEvent, type KeyboardEvent } from "react";
import { api, formatDate, isExpired, localDay, refreshData, tiers, type Pact, type Tier } from "@/lib/api";
import { brokenToday, pactDays, pactStreak } from "@/lib/pact-progress";
import { directionOf, directionPoint, directions, directionSummary, tierOrder, type DirectionName } from "@/lib/directions";
import { Action, ErrorMessage, Icon, Modal } from "./ui";
import { PactBreakAction, StreakSummary } from "./pact-streak";

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
    {mode === "move" && <Modal title="Перенести пакт" onClose={() => setMode(null)}><form className="form-stack" onSubmit={move}><p className="muted">{pact.title}. Даты, условия и история сохранятся.</p><label>Направление<select name="category" defaultValue={directionOf(pact)}>{directions.map(direction => <option key={direction.id}>{direction.name}</option>)}</select></label><p className="form-caption">В каждом направлении может быть любое количество пактов.</p><ErrorMessage error={error}/><button className="button button-red" disabled={busy}>{busy ? "Переносим…" : "Перенести пакт"}</button></form></Modal>}
    {mode === "cancel" && <Modal title="Отменить пакт?" onClose={() => setMode(null)}><p className="detail-description">{pact.title}</p><p className="muted">Пакт перейдёт в историю. Накопленные дни и история срывов сохранятся.{pact.is_joint && " Совместный пакт завершит действие для обоих участников."}</p><Action className="button-red full-width" onClick={async () => {await api(`/my/pacts/${pact.id}/cancel`, "POST");setMode(null);refreshData();}}>Отменить пакт</Action></Modal>}
  </>;
}

export function PactSeal({ pacts: records, onCreate, initialCategory = null, initialPactId = null }: { pacts: Pact[]; initialCategory?: DirectionName | null; initialPactId?: number | null; onCreate?: (category: DirectionName, tier: Tier) => void }) {
  const active = records.filter(pact => pact.status === "active");
  const target = active.find(pact => pact.id === initialPactId);
  const [chosen, setChosen] = useState<DirectionName | null>(target ? directionOf(target) : initialCategory);
  const [chosenTier, setTier] = useState<Tier | null>(target?.rarity ?? null); const [selectedId, setSelectedId] = useState<number | null>(target?.id ?? null);
  const [limit, setLimit] = useState(8);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]); const panelId = useId();
  const category = chosen ?? directions.find(direction => active.some(pact => directionOf(pact) === direction.name))?.name ?? "Тело";
  const direction = directions.find(item => item.name === category)!;
  const summary = directionSummary(active, category);
  const tier = chosenTier ?? tierOrder.find(value => summary.counts[value] > 0) ?? "common";
  const pacts = summary.active.filter(pact => pact.rarity === tier);
  const selected = pacts.find(pact => pact.id === selectedId) ?? pacts[0];
  const visiblePacts = pacts.slice(0, limit);
  if (selected && !visiblePacts.some(pact => pact.id === selected.id)) visiblePacts.push(selected);
  const today = localDay(); const eligible = directions.reduce((total, item) => total + directionSummary(active, item.name, today).eligible, 0);
  const done = directions.reduce((total, item) => total + directionSummary(active, item.name, today).checked, 0);
  function choose(name: DirectionName) {setChosen(name);setTier(null);setSelectedId(null);setLimit(8);}
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
    <div className="hex-heading"><div><h2>Карта пактов</h2><p>Шесть направлений. Любое количество обещаний.</p></div><span>{active.length}<small>активных пактов</small></span></div>
    <div className="hex-layout">
      <div className="hex-visual"><div className="hex-art">
        <svg className="hex-lines" viewBox="0 0 640 640" fill="none" aria-hidden="true"><polygon points={[0,3,4,5,2,1].map(index => {const point=directionPoint(directions[index].angle);return `${point.x},${point.y}`;}).join(" ")}/>{directions.map(item => {const point = directionPoint(item.angle);return <path key={item.id} d={`M320 320 ${point.x} ${point.y}`}/>;})}</svg>
        <svg className="hex-lines hex-lines-mobile" viewBox="0 0 640 640" preserveAspectRatio="none" fill="none" aria-hidden="true"><polygon points="320,64 498,186 498,454 320,576 142,454 142,186"/>{[[320,64],[498,186],[498,454],[320,576],[142,454],[142,186]].map(([x,y],index)=><path key={index} d={`M320 320 ${x} ${y}`}/>)}</svg>
        <div className="hex-core"><span lang="ja" aria-hidden="true">念</span>{eligible > 0 ? <><strong>{done}<i>/</i>{eligible}</strong><small>без срыва сегодня</small></> : <small>{active.length ? "сроки завершены" : "нет пактов"}</small>}</div>
        {directions.map((item, index) => {
          const point = directionPoint(item.angle); const stats = directionSummary(active, item.name, today);
          return <button key={item.id} ref={element => {buttons.current[index] = element;}} className={"hex-node " + (item.name === category ? "selected" : "")} data-direction={item.id} data-angle={item.angle} aria-label={`${item.name}: ${stats.active.length} активных пактов. Сегодня ${stats.checked} из ${stats.eligible}`} aria-pressed={item.name === category} aria-controls={panelId} style={{left:point.x/640*100+"%",top:point.y/640*100+"%","--direction-color":item.color} as CSSProperties} onClick={() => choose(item.name)} onFocus={() => {if(chosen !== item.name) choose(item.name);}} onKeyDown={event => keyboard(event,index)}>
            <span className="hex-node-symbol"><svg viewBox="0 0 84 84" fill="none" aria-hidden="true"><circle className="hex-node-track" cx="42" cy="42" r="37"/>{stats.eligible > 0 && <circle className="hex-node-progress" data-today-progress={stats.todayProgress} cx="42" cy="42" r="37" pathLength="100" strokeDasharray={`${stats.todayProgress} 100`} transform="rotate(-90 42 42)"/>}</svg><span lang="ja" aria-hidden="true">{item.glyph}</span></span>
            <strong>{item.name}</strong><small>{stats.active.length} пактов{stats.eligible > 0 && <b> · {stats.checked}/{stats.eligible} ✓</b>}</small>
          </button>;
        })}
      </div><p className="hex-explanation"><Icon name="flame" size={24}/>Серии растут автоматически. Нажми на направление.</p></div>
      <div className="hex-panel" id={panelId} style={{"--direction-color":direction.color} as CSSProperties}>
        <header className="hex-panel-heading"><div><p>НАПРАВЛЕНИЕ</p><h3>{direction.name}</h3></div><span>{summary.active.length}</span></header><p className="hex-panel-description">{direction.description}</p>
        <p className="hex-panel-daily"><Icon name="flame" size={24}/>{summary.eligible ? <>Без срыва сегодня <strong>{summary.checked} из {summary.eligible}</strong></> : "Нет действующих серий"}</p>
        <div className="hex-tier-tabs" aria-label={"Тиры направления «" + category + "»"}>{tierOrder.map(value => <button key={value} data-tier={value} className={tier === value ? "active" : ""} aria-pressed={tier === value} onClick={() => {setTier(value);setSelectedId(null);setLimit(8);}}><span className={"tier tier-"+value}>{tiers[value].label}</span><strong>{summary.counts[value]}</strong></button>)}</div>
        <div className="hex-pact-slots" aria-label={`${category}, ${tiers[tier].label}: ${pacts.length} пактов`}>
          {visiblePacts.map((pact,index) => <button key={pact.id} className={"hex-pact-slot " + (selected?.id === pact.id ? "selected" : "")} data-pact-id={pact.id} aria-pressed={selected?.id === pact.id} onClick={() => setSelectedId(pact.id)}><span className="hex-slot-number">{String(index+1).padStart(2,"0")}</span><span><strong>{pact.title}</strong><small>{pact.is_joint ? "Совместный" : "Личный пакт"}{isExpired(pact) ? " · срок истёк" : brokenToday(pact,today) ? " · срыв сегодня" : ` · серия ${pactStreak(pact)} дн.`}</small></span><b>{pact.progress === null ? "∞" : pact.progress + "%"}</b></button>)}
        </div>
        {pacts.length > limit && <button className="button button-quiet hex-pact-load-more" onClick={()=>setLimit(limit+8)}>Ещё пакты ({pacts.length-limit})<Icon name="chevron"/></button>}
        {onCreate && <button className="hex-add-pact button full-width" onClick={()=>onCreate(category,tier)}><Icon name="plus"/>Добавить {tiers[tier].label}</button>}
        {selected ? <div className="hex-pact-detail" key={selected.id}>
          <div className="hex-detail-meta"><span className={"tier tier-"+selected.rarity}>{tiers[selected.rarity].label}</span>{selected.is_joint && <span><Icon name="link" size={17}/>Совместный пакт</span>}</div><h4>{selected.title}</h4><p className="hex-conditions">{selected.description}</p>
          <StreakSummary pact={selected}/><div className="hex-progress-summary"><strong>{selected.progress === null ? "∞" : selected.progress + "%"}</strong><span>{selected.duration_days ? `${pactDays(selected)} из ${selected.duration_days} дней соблюдения` : `Дней соблюдения: ${pactDays(selected)}`}</span></div>
          {selected.progress !== null && <div className="hex-pact-progress" role="progressbar" aria-label={"Прогресс: "+selected.title} aria-valuemin={0} aria-valuemax={100} aria-valuenow={selected.progress}><span style={{width:Math.max(0,Math.min(100,selected.progress))+"%"}}/></div>}
          <div className="hex-deadline"><Icon name="calendar" size={18}/>{selected.deadline ? "До "+formatDate(selected.deadline) : "Без конечной даты"}</div>
          {isExpired(selected) ? selected.can_manage ? <Action className="full-width" onClick={async () => {await api(`/my/pacts/${selected.id}/complete`,"POST");refreshData();}}>Завершить пакт <Icon name="check"/></Action> : <p className="muted">Срок истёк. Завершить совместный пакт может автор.</p> : <PactBreakAction pact={selected}/>}
          {selected.tracking_started_on && <p className="form-caption">Автоматический отсчёт с {formatDate(selected.tracking_started_on)}. Ежедневные отметки не нужны.</p>}
          <Link className="hex-discussion" href={`/forum?pact=${selected.id}`}>Обсуждение <Icon name="message" size={19}/></Link>
          {selected.template_id && <Link className="hex-discussion" href={`/forum?topic=${selected.template_id}`}>Архив обсуждения <Icon name="book" size={19}/></Link>}
          <ManagePact pact={selected}/>
        </div> : <div className="hex-empty"><p>{active.length ? "В этом тире пока нет пактов. Создай собственный." : "Нет активных пактов. Выбери направление и заключи первый пакт."}</p>{!onCreate && <Link className="text-link" href={`/?category=${encodeURIComponent(category)}&tier=${tier}`}>Создать свой пакт <Icon name="arrow"/></Link>}</div>}
      </div>
    </div>
  </section>;
}
