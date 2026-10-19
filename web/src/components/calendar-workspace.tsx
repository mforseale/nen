"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type CSSProperties } from "react";
import { useAuth } from "@/lib/auth";
import { api, refreshData, useApi, type Calendar, type Entry, type EntryKind } from "@/lib/api";
import { addDays, calendarThemes, dayKey, entryKinds, isOverdue, longDay, parseDay, periodFor, sortEntries, type PlannerView } from "@/lib/calendar";
import { CalendarEditor, EntryEditor } from "./calendar-editors";
import { Action, Empty, ErrorMessage, Icon, Loading, Modal, PageTitle } from "./ui";

function PlannerEntry({ entry, calendars, compact = false, onEdit }: {
  entry: Entry; calendars: Calendar[]; compact?: boolean; onEdit: (entry: Entry) => void;
}) {
  const calendar = calendars.find(c => c.id === entry.calendar_id);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const overdue = isOverdue(entry);
  async function toggle() {
    setBusy(true); setError(null);
    try { await api("/calendar-entries/" + entry.id, "PATCH", { completed: !entry.completed }); refreshData(); }
    catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <article className={`planner-entry ${compact ? "compact" : ""} ${entry.completed ? "completed" : ""} ${overdue ? "overdue" : ""}`} data-priority={entry.priority} style={{ "--entry-color": calendar?.color ?? "#b9828b" } as CSSProperties}>
    <div className="planner-entry-main">
      {entry.kind === "task" ? <button className="planner-task-check" aria-pressed={entry.completed} aria-label={(entry.completed ? "Вернуть в план: " : "Выполнить: ") + entry.title} disabled={busy} onClick={toggle}>{entry.completed && <Icon name="check" size={14}/>}</button> : <span className="planner-entry-kind"><Icon name={entryKinds[entry.kind].icon} size={compact ? 14 : 19}/></span>}
      <button className="planner-entry-open" onClick={() => onEdit(entry)} aria-label={"Открыть запись: " + entry.title}>
        {compact ? <><span className="planner-compact-time">{entry.start_time}</span><span className="planner-entry-title">{entry.title}</span></> : <><strong>{entry.title}</strong><span className="planner-entry-meta">{entry.start_time ? entry.start_time + (entry.end_time ? " – " + entry.end_time : "") : "Весь день"}<i/>{calendar?.name}<i/>{entryKinds[entry.kind].label}{entry.priority === "high" && <b>Высокий приоритет</b>}{overdue && <b>Просрочено</b>}</span>{entry.description && <span className="planner-entry-description">{entry.description}</span>}</>}
      </button>
      {entry.priority === "high" && <span className="planner-priority" aria-label="Высокий приоритет">!</span>}
    </div>
    <ErrorMessage error={error}/>
  </article>;
}

export function CalendarWorkspace({ calendarId }: { calendarId?: number }) {
  const { user } = useAuth(); const router = useRouter();
  const calendarsApi = useApi<Calendar[]>(user ? "/calendars" : null);
  const ownApi = useApi<Calendar>(user && calendarId ? "/calendars/" + calendarId : null);
  const calendars = calendarsApi.data ?? [];
  const current = calendarId ? ownApi.data ?? calendars.find(c => c.id === calendarId) : undefined;
  const [anchor, setAnchor] = useState(() => new Date());
  const [view, setView] = useState<PlannerView>(() => typeof window !== "undefined" && window.matchMedia("(max-width: 680px)").matches ? "agenda" : "month");
  const [selected, setSelected] = useState<number[] | null>(null);
  const [selectedDay, setSelectedDay] = useState(() => dayKey(new Date()));
  const [dayDialog, setDayDialog] = useState<string | null>(null);
  const [editor, setEditor] = useState<{ day: string; entry?: Entry } | null>(null);
  const [calendarEditor, setCalendarEditor] = useState<Calendar | "new" | null>(null);
  const [remove, setRemove] = useState<Calendar | null>(null);
  const [kindFilter, setKindFilter] = useState<EntryKind | "all">("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [query, setQuery] = useState("");
  const period = periodFor(anchor, view);
  const entriesApi = useApi<Entry[]>(user ? "/calendar-entries?start=" + dayKey(period.start) + "&end=" + dayKey(period.end) + (calendarId ? "&calendar_id=" + calendarId : "") : null);
  const selectedIds = calendarId ? [calendarId] : selected ?? calendars.map(c => c.id);
  const scoped = (entriesApi.data ?? []).filter(entry => selectedIds.includes(entry.calendar_id));
  const visible = sortEntries(scoped.filter(entry => (kindFilter === "all" || entry.kind === kindFilter) &&
    (statusFilter === "all" || (entry.kind === "task" && (statusFilter === "completed" ? entry.completed : statusFilter === "overdue" ? isOverdue(entry) : !entry.completed))) &&
    (entry.title + " " + entry.description).toLowerCase().includes(query.toLowerCase())));
  const summary = scoped.filter(entry => view !== "month" || entry.day.slice(0, 7) === dayKey(anchor).slice(0, 7));
  const tasks = summary.filter(entry => entry.kind === "task");
  const done = tasks.filter(entry => entry.completed).length;
  const today = dayKey(new Date());
  const grouped = Array.from(new Set(visible.map(entry => entry.day)));
  const theme = current?.theme ?? "classic";
  const themeInfo = calendarThemes.find(item => item.id === theme);
  const heading = view === "week" ? period.start.toLocaleDateString("ru-RU", { day: "numeric", month: "short" }) + " — " + period.end.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" }) : anchor.toLocaleDateString("ru-RU", { month: "long", year: "numeric" }).replace(" г.", "");

  function newEntry(day = selectedDay) { setDayDialog(null); setEditor({ day }); }
  function editEntry(entry: Entry) { setDayDialog(null); setEditor({ day: entry.day, entry }); }
  function movePeriod(direction: number) {
    const next = view === "week" ? addDays(anchor, direction * 7) : new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1, 12);
    setAnchor(next); setSelectedDay(dayKey(next));
  }
  function chooseDay(day: string) { setSelectedDay(day); setDayDialog(day); }

  if (calendarsApi.loading || (calendarId && ownApi.loading)) return <Loading/>;
  if (calendarsApi.error || (calendarId && ownApi.error)) return <><PageTitle title="Календари"/><ErrorMessage error={calendarsApi.error ?? ownApi.error}/><Link className="button" href="/calendars">Все календари</Link></>;

  return <div className="planner" data-theme={theme} style={{ "--cal-accent": current?.color ?? "#d57b88" } as CSSProperties}>
    {calendarId && <Link href="/calendars" className="planner-back">← Все календари</Link>}
    <PageTitle title={current?.name ?? "Календари"}>
      <div className="planner-title-actions">{current ? <button className="button" onClick={() => setCalendarEditor(current)}><Icon name="settings" size={18}/>Настройки</button> : <button className="button" disabled={calendars.length >= 10} onClick={() => setCalendarEditor("new")}><Icon name="calendar" size={18}/>Новый календарь</button>}<button className="button button-light" disabled={!calendars.length} onClick={() => newEntry()}><Icon name="plus" size={18}/>Запланировать</button></div>
    </PageTitle>
    <p className="page-intro">{current ? <><span className="planner-color-dot"/>Отдельный календарь<span className="planner-intro-separator">·</span>{themeInfo?.label}</> : "Задачи, события и заметки. Выбирай календари для общего просмотра или открывай их отдельно."}</p>

    <div className="planner-layout">
      <aside className="planner-sidebar">
        <Link className={"planner-overview " + (!calendarId && selected === null ? "active" : "")} href="/calendars" onClick={() => setSelected(null)}><Icon name="calendar" size={19}/><span>Все календари</span><span>{calendars.length}/10</span></Link>
        <div className="planner-sidebar-heading"><h2>Мои календари</h2><button className="icon-button" aria-label="Создать календарь" disabled={calendars.length >= 10} onClick={() => setCalendarEditor("new")}><Icon name="plus" size={19}/></button></div>
        <div className="planner-calendar-list">{calendars.map(calendar => <div key={calendar.id} className={"planner-calendar-option " + (calendarId === calendar.id ? "active" : "")} style={{ "--item-color": calendar.color } as CSSProperties}>
          {!calendarId && <label className="planner-calendar-toggle"><input type="checkbox" checked={selectedIds.includes(calendar.id)} onChange={() => setSelected(selectedIds.includes(calendar.id) ? selectedIds.filter(id => id !== calendar.id) : [...selectedIds, calendar.id])}/><span>{selectedIds.includes(calendar.id) && <Icon name="check" size={13}/>}</span><span className="sr-only">Показывать {calendar.name} в общем виде</span></label>}
          <Link href={"/calendars/" + calendar.id} className="planner-calendar-link"><span className="planner-calendar-name">{calendar.name}</span><small>{calendarThemes.find(item => item.id === calendar.theme)?.label ?? "Классический"}<Icon name="arrow" size={12}/></small></Link>
          <button className="icon-button" aria-label={"Настройки календаря «" + calendar.name + "»"} onClick={() => setCalendarEditor(calendar)}><Icon name="settings" size={16}/></button>
        </div>)}</div>
        {!calendars.length && <p className="planner-sidebar-empty">Создай первый календарь, чтобы планировать задачи и события.</p>}
        {!calendarId && calendars.length > 0 && <p className="planner-sidebar-hint">Выбрано: {selectedIds.length}. Нажми на название, чтобы открыть календарь отдельно.</p>}
        {current && <div className="planner-theme-description"><Icon name={themeInfo?.icon ?? "calendar"} size={24}/><strong>{themeInfo?.label}</strong><p>{themeInfo?.description}</p><button className="text-link" onClick={() => setCalendarEditor(current)}>Изменить оформление →</button><button className="planner-remove-calendar" onClick={() => setRemove(current)}><Icon name="trash" size={15}/>Удалить календарь</button></div>}
        <div className="planner-legend"><span><i className="legend-task"/>Задача</span><span><i className="legend-event"/>Событие</span><span><i className="legend-note"/>Заметка</span></div>
      </aside>

      <section className="planner-board" aria-label={current ? "Планы: " + current.name : "Общий календарь"}>
        <div className="planner-summary"><div><strong>{tasks.length - done}</strong><span>Запланировано задач</span></div><div><strong>{done}<small> / {tasks.length}</small></strong><span>Задач выполнено</span></div><div><strong>{summary.filter(entry => entry.kind === "event").length}</strong><span>Событий</span></div><div><strong>{summary.length}</strong><span>Всего записей</span></div></div>
        <div className="planner-toolbar"><div className="planner-period"><button className="icon-button" aria-label="Предыдущий период" onClick={() => movePeriod(-1)}>←</button><h2>{heading}</h2><button className="icon-button" aria-label="Следующий период" onClick={() => movePeriod(1)}>→</button><button className="button planner-today" onClick={() => {setAnchor(new Date());setSelectedDay(today);}}>Сегодня</button></div><div className="planner-view-switch" role="group" aria-label="Вид календаря">{([{id:"month",label:"Месяц",icon:"grid"},{id:"week",label:"Неделя",icon:"calendar"},{id:"agenda",label:"Список",icon:"list"}] as const).map(item => <button key={item.id} className={view === item.id ? "active" : ""} aria-pressed={view === item.id} onClick={() => setView(item.id)}><Icon name={item.icon} size={16}/>{item.label}</button>)}</div></div>
        <div className="planner-filters"><div className="planner-record-search"><Icon name="search" size={17}/><input aria-label="Поиск по записям календаря" placeholder="Найти запись…" value={query} onChange={event => setQuery(event.target.value)}/></div><select aria-label="Тип записей" value={kindFilter} onChange={event => setKindFilter(event.target.value as EntryKind | "all")}><option value="all">Все записи</option><option value="task">Задачи</option><option value="event">События</option><option value="note">Заметки</option></select><select aria-label="Статус задач" value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="all">Любой статус</option><option value="planned">Задачи в плане</option><option value="completed">Выполненные</option><option value="overdue">Просроченные</option></select></div>
        <ErrorMessage error={entriesApi.error}/>
        {entriesApi.loading ? <Loading/> : view === "agenda" ? <div className="planner-agenda">{grouped.length ? grouped.map(day => <section key={day} className={day === today ? "is-today" : ""}><div className="planner-agenda-date"><h3>{longDay(day)}</h3><button className="text-link" onClick={() => newEntry(day)}><Icon name="plus" size={16}/>Добавить</button></div>{visible.filter(entry => entry.day === day).map(entry => <PlannerEntry key={entry.id} entry={entry} calendars={calendars} onEdit={editEntry}/>)}</section>) : <Empty title="Записей не найдено"><p>Измени фильтры или запланируй задачу на выбранный период.</p><button className="button" disabled={!calendars.length} onClick={() => newEntry()}>Запланировать <Icon name="plus" size={17}/></button></Empty>}</div> : <div className="planner-grid-scroll"><div className={"planner-days " + (view === "week" ? "week-view" : "month-view")}>
          {Array.from({length: view === "week" ? 7 : 42}, (_, index) => {
            const date = addDays(period.start, index); const day = dayKey(date); const items = visible.filter(entry => entry.day === day); const limit = view === "week" ? 30 : 3;
            return <div key={day} className={"planner-day " + (day === today ? "is-today " : "") + (day === selectedDay ? "is-selected " : "") + (view === "month" && date.getMonth() !== anchor.getMonth() ? "other-month" : "")}>
              {(view === "week" || index < 7) && <span className="planner-weekday">{date.toLocaleDateString("ru-RU",{weekday:"short"})}</span>}
              <div className="planner-day-header"><button className="planner-day-number" onClick={() => chooseDay(day)} aria-label={longDay(day) + ", записей: " + items.length}>{date.getDate()}{view === "week" && <small>{date.toLocaleDateString("ru-RU",{month:"short"})}</small>}</button><button className="planner-day-add" aria-label={"Добавить запись на " + longDay(day)} disabled={!calendars.length} onClick={() => newEntry(day)}><Icon name="plus" size={14}/></button></div>
              <div className="planner-day-records">{items.slice(0, limit).map(entry => <PlannerEntry key={entry.id} entry={entry} calendars={calendars} compact onEdit={editEntry}/>)}{items.length > limit && <button className="planner-more" onClick={() => chooseDay(day)}>Ещё {items.length - limit} →</button>}</div>
              {view === "week" && !items.length && <button className="planner-week-empty" disabled={!calendars.length} onClick={() => newEntry(day)}>+ Запланировать</button>}
            </div>;
          })}
        </div></div>}
        <div className="planner-board-footer"><span><Icon name="check" size={15}/>Галочка завершает задачу. Нажатие на запись открывает редактирование.</span><span>{current ? current.name : "Выбрано календарей: " + selectedIds.length}</span></div>
      </section>
    </div>

    {calendarEditor && <CalendarEditor calendar={calendarEditor === "new" ? undefined : calendarEditor} calendars={calendars} onClose={() => setCalendarEditor(null)} onRemove={calendar => {setCalendarEditor(null);setRemove(calendar);}} onSaved={saved => {const created = calendarEditor === "new";setCalendarEditor(null);if(created) router.push("/calendars/" + saved.id);}}/>}
    {editor && <EntryEditor entry={editor.entry} day={editor.day} calendarId={calendarId ?? selectedIds[0]} calendars={calendars} onClose={() => setEditor(null)} onSaved={entry => {setEditor(null);setSelectedDay(entry.day);setAnchor(parseDay(entry.day));if(calendarId && entry.calendar_id !== calendarId) router.push("/calendars/" + entry.calendar_id);else if(!calendarId && selected && !selected.includes(entry.calendar_id)) setSelected([...selected,entry.calendar_id]);}}/>}
    {dayDialog && <Modal title={longDay(dayDialog)} onClose={() => setDayDialog(null)}><div className="planner-day-dialog-list">{visible.filter(entry => entry.day === dayDialog).length ? visible.filter(entry => entry.day === dayDialog).map(entry => <PlannerEntry key={entry.id} entry={entry} calendars={calendars} onEdit={editEntry}/>) : <p className="detail-description">На этот день нет записей с выбранными фильтрами.</p>}</div><button className="button button-red full-width" disabled={!calendars.length} onClick={() => newEntry(dayDialog)}>Запланировать <Icon name="plus" size={18}/></button></Modal>}
    {remove && <Modal title="Удалить календарь?" onClose={() => setRemove(null)}><p className="detail-description">«{remove.name}» будет удалён вместе со всеми задачами, событиями и заметками.</p><Action className="button-red" onClick={async () => {await api("/calendars/" + remove.id, "DELETE");setRemove(null);if(calendarId === remove.id) router.push("/calendars");refreshData();}}>Удалить календарь <Icon name="trash" size={17}/></Action></Modal>}
  </div>;
}
