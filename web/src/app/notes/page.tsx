"use client";
import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { formatDate, useApi, type Note } from "@/lib/api";
import RequireAuth from "@/components/require-auth";
import { NoteEditor } from "@/components/note-editor";
import { Empty, ErrorMessage, Icon, Loading, PageTitle, Shell } from "@/components/ui";

const visibilityLabels = {private:"Только я",invited:"По приглашению",public:"Открытая запись"};const visibilityIcons = {private:"lock",invited:"user",public:"globe"};
function Notes() {
 const {user} = useAuth();const {data,loading,error} = useApi<Note[]>(user ? "/notes" : null);const [create,setCreate] = useState(false);const [tab,setTab] = useState("all");
 const notes = data?.filter(n => tab === "shared" ? n.author.id !== user?.id : n.author.id === user?.id && (tab === "all" || n.visibility === tab)) ?? [];
 return <><PageTitle title="Заметки"><button className="button button-light" onClick={() => setCreate(true)}>Новая заметка <Icon name="plus" size={17}/></button></PageTitle><p className="page-intro">Личные записи, публикации и заметки, доступные по приглашению.</p><div className="plain-tabs standalone-tabs">{[["all","Мои записи"],["public","Открытые"],["private","Личные"],["invited","По приглашению"],["shared","Доступные мне"]].map(([id,label]) => <button className={tab === id ? "active" : ""} key={id} onClick={() => setTab(id)}>{label}</button>)}</div><ErrorMessage error={error}/>{loading ? <Loading/> : notes.length ? <div className="notes-grid">{notes.map(n => <Link href={"/notes/"+n.id} key={n.id} className="note-card"><div className="note-card-meta"><time>{formatDate(n.created_at)}</time><span><Icon name={visibilityIcons[n.visibility]} size={13}/>{visibilityLabels[n.visibility]}</span></div><h2>{n.title}</h2><p>{n.content}</p><div className="note-card-bottom"><span>@{n.author.username}</span><Icon name="arrow" size={18}/></div></Link>)}</div> : !error && <Empty title={tab === "shared" ? "Здесь появятся приглашения" : "Заметок пока нет"}><p>{tab === "shared" ? "Когда другой пользователь откроет тебе заметку, она появится здесь." : "Создай заметку и выбери, кто сможет её прочитать."}</p>{tab !== "shared" && <button className="button" onClick={() => setCreate(true)}>Начать запись <Icon name="feather" size={17}/></button>}</Empty>}{create && <NoteEditor onClose={() => setCreate(false)}/>}</>;
}
export default function NotesPage(){return <Shell><RequireAuth><Notes/></RequireAuth></Shell>;}
