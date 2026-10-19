"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { api, refreshData, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { profileHref } from "@/lib/profile-navigation";
import type { Friendship } from "@/lib/community";
import RequireAuth from "@/components/require-auth";
import { Avatar } from "@/components/profile-sections";
import { Action, Empty, ErrorMessage, Icon, Loading, PageTitle, Shell } from "@/components/ui";

function Friends() {
  const { user } = useAuth(); const { data, loading, error } = useApi<Friendship[]>(user ? "/friends" : null);
  const [chosenTab, setTab] = useState<string | null>(null); const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false); const [sendError, setSendError] = useState<string | null>(null); const [message, setMessage] = useState("");
  const incoming = data?.filter(item => item.status === "pending" && item.incoming) ?? [];
  const friends = data?.filter(item => item.status === "accepted") ?? [];
  const outgoing = data?.filter(item => item.status === "pending" && !item.incoming) ?? [];
  const tab = chosenTab ?? (incoming.length ? "incoming" : "friends");
  const items = (tab === "friends" ? friends : tab === "incoming" ? incoming : outgoing).filter(item => (item.person.full_name + " " + item.person.username).toLowerCase().includes(query.toLowerCase()));
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const username = new FormData(form).get("username"); setBusy(true);setSendError(null);setMessage("");
    try { await api("/friends", "POST", { username });setMessage("Заявка отправлена. Дружба начнётся после подтверждения.");form.reset();setTab("outgoing");refreshData(); }
    catch (error) {setSendError((error as Error).message);} finally {setBusy(false);}
  }
  return <><PageTitle title="Друзья"><Link className="button button-quiet" href={profileHref(user?.username)}>Мой профиль <Icon name="user" size={17}/></Link></PageTitle><p className="page-intro">Добавляй людей, с которыми хочешь поддерживать связь и делиться своим путём.</p>
    <section className="friend-invite-panel"><div><h2><Icon name="friends" size={22}/>Добавить друга</h2><p>Введи логин. Найти человека по имени можно через поиск в навбаре.</p></div><form className="friend-invite-form" onSubmit={send}><label className="sr-only" htmlFor="friend-username">Логин друга</label><input id="friend-username" name="username" required minLength={3} maxLength={51} placeholder="@username" autoComplete="off"/><button className="button button-red" disabled={busy}>{busy ? "Отправляем…" : "Отправить заявку"}<Icon name="plus" size={16}/></button></form><ErrorMessage error={sendError}/>{message && <p className="success-message" role="status">{message}</p>}</section>
    <div className="friends-toolbar"><div className="plain-tabs"><button className={tab === "friends" ? "active" : ""} onClick={() => setTab("friends")}>Друзья <span>{friends.length}</span></button><button className={tab === "incoming" ? "active" : ""} onClick={() => setTab("incoming")}>Входящие <span>{incoming.length}</span></button><button className={tab === "outgoing" ? "active" : ""} onClick={() => setTab("outgoing")}>Отправленные <span>{outgoing.length}</span></button></div><label className="friends-search"><Icon name="search" size={17}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Найти в списке" aria-label="Поиск в списке друзей"/></label></div>
    <ErrorMessage error={error}/>{loading ? <Loading/> : items.length ? <div className="friends-list">{items.map(item => <article className="friend-row" key={item.id}><Link href={"/people/" + item.person.username} className="friend-person"><Avatar person={item.person}/><span><strong>{item.person.full_name}</strong><small>@{item.person.username}</small></span></Link><div className="friend-row-actions">{tab === "incoming" ? <><Action className="button-red" onClick={async () => {await api(`/friends/${item.id}/respond`, "POST", {accept:true});refreshData();}}>Принять <Icon name="check" size={15}/></Action><Action className="button-quiet" onClick={async () => {await api(`/friends/${item.id}/respond`, "POST", {accept:false});refreshData();}}>Отклонить</Action></> : <><Link className="text-link" href={"/people/" + item.person.username}>Профиль <Icon name="arrow" size={16}/></Link><Action className="button-quiet" onClick={async () => {await api(`/friends/${item.id}`, "DELETE");refreshData();}}>{tab === "friends" ? "Убрать из друзей" : "Отменить заявку"}</Action></>}</div></article>)}</div> : !error && <Empty title={query ? "Никого не найдено" : tab === "friends" ? "Друзей пока нет" : tab === "incoming" ? "Нет новых заявок" : "Нет отправленных заявок"}><p>{query ? "Попробуй другое имя или логин." : "Отправь заявку по логину или открой профиль через поиск пользователей."}</p></Empty>}
  </>;
}

export default function FriendsPage() {return <Shell><RequireAuth><Friends/></RequireAuth></Shell>;}
