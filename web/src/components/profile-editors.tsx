"use client";
/* eslint-disable @next/next/no-img-element -- Local previews and authenticated user images bypass the shared image optimizer. */

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { api, refreshData, tiers, useApi, type Pact, type Tier } from "@/lib/api";
import { type Capacity, type DirectionName } from "@/lib/directions";
import { useAuth } from "@/lib/auth";
import { profileHref } from "@/lib/profile-navigation";
import { audiences, pactCategories, prepareImage, type Audience, type ProfileData, type YearGoal } from "@/lib/community";
import { ErrorMessage, Icon, Modal } from "./ui";

export function AudienceSelect({ value = "private" }: { value?: Audience }) {
  return <label>Кто видит<select name="visibility" defaultValue={value}>{Object.entries(audiences).map(([key, title]) => <option key={key} value={key}>{title}</option>)}</select></label>;
}

export function PersonalPactForm({ onClose, defaultCategory = "Другое", defaultRarity = "common" }: { onClose: () => void; defaultCategory?: DirectionName; defaultRarity?: Tier }) {
  const router = useRouter();
  const {user} = useAuth();
  const [rarity, setRarity] = useState<Tier>(defaultRarity);
  const [category, setCategory] = useState<DirectionName>(defaultCategory);
  const capacity = useApi<Capacity>("/my/pacts/capacity");
  const occupied = capacity.data?.counts[category]?.[rarity] ?? 0;
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError(null);
    try {
      const pact = await api<Pact>("/my/pacts", "POST", { title: form.get("title"), description: form.get("description"), rarity, category: form.get("category") });
      refreshData(); onClose(); router.push(profileHref(user?.username,`pact=${pact.id}`,"pacts"));
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <Modal title="Свой пакт" onClose={onClose}><form className="form-stack" onSubmit={submit}>
    <p className="muted">Сформулируй конкретное ежедневное действие. Пакт будет виден только тебе и сразу появится на карте пактов.</p>
    <label>Название<input name="title" required minLength={3} maxLength={150} placeholder="Например, заниматься японским каждый день"/></label>
    <label>Условия<textarea name="description" required minLength={10} maxLength={5000} placeholder="Что именно и сколько ты будешь делать каждый день?"/></label>
    <div className="profile-form-grid"><label>Уровень<select value={rarity} onChange={event => setRarity(event.target.value as Tier)}>{(Object.keys(tiers) as Tier[]).map(tier => <option key={tier} value={tier}>{tiers[tier].label} · {tiers[tier].duration}</option>)}</select></label>
    <label>Направление<select name="category" value={category} onChange={event => setCategory(event.target.value as DirectionName)}>{pactCategories.map(category => <option key={category}>{category}</option>)}</select></label></div>
    <p className={occupied >= 3 ? "error-message" : "capacity-notice"}>{capacity.loading ? "Проверяем свободные места…" : `${category} · ${tiers[rarity].label}: занято ${occupied} из 3 мест.`}{occupied >= 3 && " Заверши, перенеси или отмени один из активных пактов."}</p>
    <p className="form-caption">Длительность: {tiers[rarity].duration}. Условия фиксируются при заключении.</p>
    <ErrorMessage error={error ?? capacity.error}/><button className="button button-red full-width" disabled={busy || capacity.loading || !!capacity.error || occupied >= 3}>{busy ? "Создаём…" : "Заключить свой пакт"}<Icon name="seal" size={18}/></button>
  </form></Modal>;
}

export function SettingsForm({ profile, onClose }: { profile: ProfileData; onClose: () => void }) {
  const { refreshUser } = useAuth();
  const [image, setImage] = useState<string | null>(null); const [remove, setRemove] = useState(false);
  const [preparing, setPreparing] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError(null);
    try {
      await api("/my/profile", "PUT", { full_name: form.get("full_name"), bio: form.get("bio"), accent: form.get("accent") });
      if (image) await api("/my/profile/avatar", "PUT", { data_url: image });
      else if (remove) await api("/my/profile/avatar", "DELETE");
      await refreshUser(); refreshData(); onClose();
    } catch (error) { setError((error as Error).message); refreshData(); } finally { setBusy(false); }
  }
  const preview = image ?? (!remove ? profile.user.avatar_url : null);
  return <Modal title="Настройки профиля" onClose={onClose}><form className="form-stack" onSubmit={submit}>
    <div className="avatar-editor"><div className="person-avatar large">{preview ? <img src={preview} alt="Предпросмотр аватарки"/> : profile.user.full_name.slice(0, 1)}</div><div><label>Аватарка<input type="file" accept="image/png,image/jpeg,image/webp" disabled={busy || preparing} onChange={async event => {
      const file = event.target.files?.[0]; if (!file) return; setPreparing(true); setError(null);
      try { setImage(await prepareImage(file, true)); setRemove(false); } catch (error) { setError((error as Error).message); } finally { setPreparing(false); }
    }}/></label>{preview && <button type="button" className="text-link" onClick={() => {setRemove(true);setImage(null);}}>Убрать аватарку</button>}</div></div>
    <p className="form-caption">PNG, JPEG или WebP до 10 МиБ. Аватарка обрезается по центру. Имя, описание и аватар видны всем.</p>
    <label>Отображаемое имя<input name="full_name" defaultValue={profile.user.full_name} required minLength={2} maxLength={120}/></label>
    <label>О себе<textarea name="bio" defaultValue={profile.bio} maxLength={2000} placeholder="Несколько слов о себе и своём пути"/></label>
    <label>Акцент профиля<select name="accent" defaultValue={profile.accent}><option value="crimson">Гранатовый</option><option value="silver">Серебряный</option><option value="gold">Состаренное золото</option></select></label>
    <ErrorMessage error={error}/><button className="button button-red full-width" disabled={busy || preparing}>{preparing ? "Готовим картинку…" : busy ? "Сохраняем…" : "Сохранить настройки"}<Icon name="check" size={17}/></button>
  </form></Modal>;
}

export function GoalEditor({ goal, year, onClose, onSaved }: { goal?: YearGoal; year: number; onClose: () => void; onSaved?: (year: number) => void }) {
  const [target, setTarget] = useState(goal?.target ?? 1);
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = new FormData(event.currentTarget); setBusy(true); setError(null);
    try {
      await api(goal ? `/my/goals/${goal.id}` : "/my/goals", goal ? "PUT" : "POST", {
        year: Number(form.get("year")), title: form.get("title"), description: form.get("description"),
        target, current: Number(form.get("current")), unit: form.get("unit"), visibility: form.get("visibility"),
      });
      onSaved?.(Number(form.get("year"))); refreshData(); onClose();
    } catch (error) { setError((error as Error).message); } finally { setBusy(false); }
  }
  return <Modal title={goal ? "Изменить цель" : "Цель на год"} onClose={onClose}><form className="form-stack" onSubmit={submit}>
    <label>Цель<input name="title" defaultValue={goal?.title} required maxLength={150} placeholder="Прочитать 12 книг"/></label>
    <label>Описание<textarea name="description" defaultValue={goal?.description} maxLength={5000} placeholder="Почему это важно и какие шаги помогут"/></label>
    <div className="profile-form-grid"><label>Год<input type="number" name="year" defaultValue={goal?.year ?? year} min={2000} max={2100} required/></label><label>Единица измерения<input name="unit" defaultValue={goal?.unit ?? "шагов"} maxLength={30} required placeholder="книг, км, проектов"/></label>
    <label>Хочу выполнить<input type="number" value={target || ""} onChange={event => setTarget(Number(event.target.value))} min={1} max={1000000000} required/></label><label>Уже выполнено<input name="current" type="number" defaultValue={goal?.current ?? 0} min={0} max={target} required/></label></div>
    <AudienceSelect value={goal?.visibility}/><ErrorMessage error={error}/><button className="button button-red full-width" disabled={busy}>{busy ? "Сохраняем…" : goal ? "Сохранить цель" : "Добавить цель"}<Icon name="target" size={17}/></button>
  </form></Modal>;
}

