"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { api, refreshData, tiers, useApi } from "@/lib/api";
import { Empty, ErrorMessage, Icon, Modal } from "./ui";
import { directions, type Capacity, type DirectionName } from "@/lib/directions";

export function JointForm({ recipient = "", onClose }: { recipient?: string; onClose: () => void }) {
  const [error,setError] = useState<string | null>(null); const [busy,setBusy] = useState(false); const [sent,setSent] = useState(false);
  const [category,setCategory] = useState<DirectionName>("Социум"); const [duration,setDuration] = useState(30);
  const {data:capacity} = useApi<Capacity>("/my/pacts/capacity");
  const tier = duration <= 7 ? "common" : duration <= 31 ? "rare" : "epic";
  const full = (capacity?.counts[category]?.[tier] ?? 0) >= 3;
  async function submit(e: FormEvent<HTMLFormElement>) {e.preventDefault();const form = new FormData(e.currentTarget);setBusy(true);setError(null);try {await api("/requests", "POST", {recipient:form.get("recipient"),title:form.get("title"),description:form.get("description"),duration_days:duration,category});setSent(true);refreshData();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <Modal title="Совместный пакт" onClose={onClose}>{sent ? <Empty title="Приглашение отправлено"><p>Пакт вступит в силу после принятия. Свободное место проверяется у обоих участников.</p><Link className="button" href="/requests">К запросам <Icon name="arrow"/></Link></Empty> : <form className="form-stack" onSubmit={submit}>
    <p className="muted">Укажи пользователя, направление, условия и собственную длительность.</p><label>Пользователь<input name="recipient" placeholder="Логин пользователя" defaultValue={recipient} required minLength={3} maxLength={50}/></label><label>Название пакта<input name="title" required minLength={3} maxLength={150}/></label><label>Ваши условия<textarea name="description" required minLength={10} maxLength={5000} placeholder="Что именно каждый из вас обязуется делать?"/></label>
    <div className="profile-form-grid"><label>Направление<select value={category} onChange={event => setCategory(event.target.value as DirectionName)}>{directions.map(item => <option key={item.id}>{item.name}</option>)}</select></label><label>Длительность, дней<input type="number" min={1} max={36500} value={duration || ""} onChange={event => setDuration(Number(event.target.value))} required/></label></div>
    <p className="capacity-notice">Уровень по длительности: <strong className={"tier tier-"+tier}>{tiers[tier].label}</strong>. Занято {capacity?.counts[category]?.[tier] ?? "…"} из 3 мест.{full && " Сначала освободи место в этом направлении."}</p>
    <ErrorMessage error={error}/><button className="button button-red full-width" disabled={busy || full}>{busy ? "Отправляем…" : "Предложить пакт"}<Icon name="link"/></button><p className="form-caption">До принятия приглашения место не резервируется.</p>
  </form>}</Modal>;
}
