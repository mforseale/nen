"use client";

import { useState, type CSSProperties, type FormEvent } from "react";
import { api, refreshData, type Calendar, type CalendarTheme, type Entry, type EntryKind } from "@/lib/api";
import { calendarColors, calendarThemes, entryKinds, longDay } from "@/lib/calendar";
import { ErrorMessage, Icon, Modal } from "./ui";

export function CalendarEditor({ calendar, calendars, onClose, onSaved, onRemove }: {
  calendar?: Calendar; calendars: Calendar[]; onClose: () => void; onSaved: (calendar: Calendar) => void; onRemove: (calendar: Calendar) => void;
}) {
  const [color, setColor] = useState(calendar?.color ?? calendarColors.find(value => !calendars.some(c => c.color === value)) ?? calendarColors[0]);
  const [theme, setTheme] = useState<CalendarTheme>(calendar?.theme ?? calendarThemes[calendars.length % calendarThemes.length].id);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const colors = [...new Set([...calendarColors, ...(calendar ? [calendar.color] : [])])];

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true); setError(null);
    try {
      const saved = await api<Calendar>(calendar ? "/calendars/" + calendar.id : "/calendars", calendar ? "PUT" : "POST", { name: form.get("name"), color, theme });
      refreshData(); onSaved(saved);
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }

  return <Modal title={calendar ? "Настройки календаря" : "Новый календарь"} onClose={onClose}>
    <form className="form-stack planner-form" onSubmit={save}>
      <label>Название<input name="name" placeholder="Например, учёба или тренировки" defaultValue={calendar?.name} maxLength={80} required/></label>
      <fieldset className="color-picker"><legend>Цвет календаря</legend>{colors.map(value => <label key={value} className={color === value ? "selected" : ""} style={{ "--calendar-color": value } as CSSProperties}><input type="radio" name="color" value={value} checked={color === value} disabled={calendars.some(c => c.id !== calendar?.id && c.color === value)} onChange={() => setColor(value)} aria-label={"Цвет " + value}/><span>{color === value && <Icon name="check" size={17}/>}</span></label>)}</fieldset>
      <fieldset className="planner-theme-options"><legend>Оформление отдельной страницы</legend>{calendarThemes.map(item => <label key={item.id} data-theme={item.id} className={theme === item.id ? "selected" : ""} style={{ "--cal-accent": color } as CSSProperties}><input type="radio" name="theme" value={item.id} checked={theme === item.id} onChange={() => setTheme(item.id)}/><span className="theme-preview"><Icon name={item.icon} size={24}/><i/><i/><i/></span><strong>{item.label}</strong><small>{item.description}</small></label>)}</fieldset>
      <ErrorMessage error={error}/><button className="button button-red full-width" disabled={busy}>{busy ? "Сохраняем…" : calendar ? "Сохранить изменения" : "Создать календарь"}<Icon name="check" size={17}/></button>
    </form>
    {calendar && <div className="planner-delete-entry"><button className="text-link" onClick={() => onRemove(calendar)}><Icon name="trash" size={16}/>Удалить календарь</button></div>}
  </Modal>;
}

export function EntryEditor({ entry, day, calendarId, calendars, onClose, onSaved }: {
  entry?: Entry; day: string; calendarId?: number; calendars: Calendar[]; onClose: () => void; onSaved: (entry: Entry) => void;
}) {
  const [kind, setKind] = useState<EntryKind>(entry?.kind ?? "task");
  const [completed, setCompleted] = useState(entry?.completed ?? false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    const start = String(form.get("start_time") ?? "");
    const end = String(form.get("end_time") ?? "");
    if (kind === "event" && end && (!start || end <= start)) {
      setError("Укажи время окончания позже начала в пределах одного дня.");
      return;
    }
    setBusy(true); setError(null);
    try {
      const saved = await api<Entry>(entry ? "/calendar-entries/" + entry.id : "/calendar-entries", entry ? "PATCH" : "POST", {
        calendar_id: Number(form.get("calendar")), title: form.get("title"), day: form.get("day"), kind,
        description: form.get("description"), start_time: kind === "note" ? null : form.get("start_time") || null,
        end_time: kind === "event" ? form.get("end_time") || null : null,
        priority: kind === "note" ? "normal" : form.get("priority"), completed: kind === "task" && completed,
      });
      refreshData(); onSaved(saved);
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }

  return <Modal title={entry ? "Редактировать запись" : "Запланировать"} onClose={onClose}>
    <form className="form-stack planner-form" onSubmit={save}>
      <fieldset className="planner-kind-options"><legend>Тип записи</legend>{(Object.keys(entryKinds) as EntryKind[]).map(value => <label key={value} className={kind === value ? "selected" : ""}><input type="radio" name="kind" checked={kind === value} onChange={() => setKind(value)}/><Icon name={entryKinds[value].icon} size={18}/>{entryKinds[value].label}</label>)}</fieldset>
      <label>Название<input name="title" placeholder={kind === "task" ? "Что нужно сделать?" : kind === "event" ? "Название события" : "Название заметки"} defaultValue={entry?.title} maxLength={150} required/></label>
      <div className="planner-form-row"><label>Дата<input name="day" type="date" defaultValue={entry?.day ?? day} required/></label><label>Календарь<select name="calendar" defaultValue={entry?.calendar_id ?? calendarId ?? calendars[0]?.id} required>{calendars.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label></div>
      {kind !== "note" && <div className="planner-form-row"><label>{kind === "task" ? "Время выполнения" : "Начало"}<input name="start_time" type="time" defaultValue={entry?.start_time ?? ""}/></label>{kind === "event" ? <label>Окончание<input name="end_time" type="time" defaultValue={entry?.end_time ?? ""}/></label> : <label>Приоритет<select name="priority" defaultValue={entry?.priority ?? "normal"}><option value="low">Низкий</option><option value="normal">Обычный</option><option value="high">Высокий</option></select></label>}</div>}
      {kind === "event" && <label>Приоритет<select name="priority" defaultValue={entry?.priority ?? "normal"}><option value="low">Низкий</option><option value="normal">Обычный</option><option value="high">Высокий</option></select></label>}
      <label>Описание<textarea name="description" placeholder="Детали, план действий или заметки" defaultValue={entry?.description} maxLength={5000}/></label>
      {kind === "task" && <label className="planner-completed-field"><input type="checkbox" checked={completed} onChange={event => setCompleted(event.target.checked)}/><span>Задача выполнена</span></label>}
      <ErrorMessage error={error}/><button className="button button-red full-width" disabled={busy}>{busy ? "Сохраняем…" : entry ? "Сохранить изменения" : "Добавить в календарь"}<Icon name="check" size={17}/></button>
    </form>
    {entry && <div className="planner-delete-entry">{confirmDelete ? <><p>Удалить «{entry.title}» за {longDay(entry.day)}?</p><div><button className="button button-red" disabled={busy} onClick={async () => {setBusy(true);setError(null);try {await api("/calendar-entries/" + entry.id, "DELETE");refreshData();onClose();}catch(error){setError((error as Error).message);}finally{setBusy(false);}}}>Удалить</button><button className="button button-quiet" disabled={busy} onClick={() => setConfirmDelete(false)}>Отмена</button></div></> : <button className="text-link" onClick={() => setConfirmDelete(true)}><Icon name="trash" size={16}/>Удалить запись</button>}</div>}
  </Modal>;
}
