"use client";
import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, formatDate, refreshData, tiers, useApi, type PactRequest } from "@/lib/api";
import type { Friendship } from "@/lib/community";
import RequireAuth from "@/components/require-auth";
import { JointForm } from "@/components/pact-detail";
import { Action, Empty, ErrorMessage, Icon, Loading, PageTitle, Shell } from "@/components/ui";

function FriendNotice() {
  const { user } = useAuth();
  const friends = useApi<Friendship[]>(user ? "/friends" : null);
  const pending = friends.data?.filter(item => item.incoming && item.status === "pending").length ?? 0;
  return <Link href="/friends" className="friend-requests-notice"><Icon name="friends" size={19}/>{pending ? `Заявки в друзья: ${pending}` : "Друзья и заявки в друзья"}<Icon name="arrow" size={17}/></Link>;
}

function Requests() {
  const {user} = useAuth();const {data,loading,error} = useApi<PactRequest[]>(user ? "/requests" : null);const [incoming,setIncoming] = useState(true);const [create,setCreate] = useState(false);
  const items = data?.filter(r => r.incoming === incoming) ?? []; const status: Record<string,string> = {pending:"Ожидает ответа",accepted:"Принят",declined:"Отклонён"};
  return <><PageTitle title="Запросы на пакты"><button className="button" onClick={() => setCreate(true)}>Предложить пакт <Icon name="plus" size={17}/></button></PageTitle><p className="page-intro">Входящие предложения и отправленные приглашения в совместные пакты.</p><div className="plain-tabs standalone-tabs"><button className={incoming ? "active" : ""} onClick={() => setIncoming(true)}>Входящие <span>{data?.filter(r => r.incoming && r.status === "pending").length ?? 0}</span></button><button className={!incoming ? "active" : ""} onClick={() => setIncoming(false)}>Отправленные</button></div><ErrorMessage error={error}/>{loading ? <Loading/> : items.length ? <div className="request-list">{items.map(r => <article className="request-row" key={r.id}><div className="request-emblem"><Icon name="link" size={26}/></div><div className="request-body"><div className="request-meta"><span className="joint-label">СОВМЕСТНЫЙ ПАКТ</span><time>{formatDate(r.created_at)}</time><span className={"request-status status-" + r.status}>{status[r.status]}</span></div><h2>{r.title}</h2><p className="request-people">{r.incoming ? "От" : "Для"} <a href={"/people/" + (r.incoming ? r.sender.username : r.recipient.username)}>@{r.incoming ? r.sender.username : r.recipient.username}</a><span>·</span>{r.duration_days} дней с момента принятия</p><p className="request-direction"><span>{r.category}</span><span className={"tier tier-" + r.rarity}>{tiers[r.rarity].label}</span></p><p className="request-conditions">{r.description}</p>{r.incoming && r.status === "pending" && <div className="request-buttons"><Action className="button-red" onClick={async () => {await api("/requests/"+r.id+"/respond","POST",{accept:true,utc_offset_minutes:-new Date().getTimezoneOffset()});refreshData();}}>Принять условия <Icon name="check" size={16}/></Action><Action className="button-quiet" onClick={async () => {await api("/requests/"+r.id+"/respond","POST",{accept:false});refreshData();}}>Отклонить</Action></div>}</div></article>)}</div> : !error && <Empty title={incoming ? "Пока нет приглашений" : "Нет отправленных запросов"}><p>Предложи другому пользователю пакт со своими условиями и сроком.</p><button className="button" onClick={() => setCreate(true)}>Предложить пакт <Icon name="arrow" size={17}/></button></Empty>}{create && <JointForm onClose={() => setCreate(false)}/>}</>;
}
export default function RequestsPage(){return <Shell><RequireAuth><FriendNotice/><Requests/></RequireAuth></Shell>;}
