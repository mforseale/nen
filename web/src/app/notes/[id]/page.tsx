"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Suspense, useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, formatDate, refreshData, useApi, type Note } from "@/lib/api";
import { NoteEditor } from "@/components/note-editor";
import { Action, ErrorMessage, Icon, Loading, Modal, Shell } from "@/components/ui";

function NoteContent() {
 const {id} = useParams<{id:string}>(); const {user} = useAuth();const router = useRouter();const {data:note,error,loading} = useApi<Note>("/notes/"+id);const [edit,setEdit] = useState(false);const [remove,setRemove] = useState(false);
 return <Shell><div className="note-reading"><Link className="back-link" href="/notes">← К заметкам</Link><ErrorMessage error={error}/>{loading ? <Loading/> : note && <><div className="note-reading-meta"><span>{formatDate(note.created_at)}</span><span><Icon name={note.visibility === "private" ? "lock" : note.visibility === "invited" ? "user" : "globe"} size={14}/>{note.visibility === "private" ? "Только я" : note.visibility === "invited" ? "По приглашению" : "Открытая запись"}</span></div><h1>{note.title}</h1><Link className="text-link" href={"/people/"+note.author.username}>@{note.author.username}</Link><div className="note-prose">{note.content}</div>{user?.id === note.author.id && <div className="note-actions"><button className="button" onClick={() => setEdit(true)}>Редактировать <Icon name="feather" size={16}/></button><button className="icon-button" onClick={() => setRemove(true)} aria-label="Удалить заметку"><Icon name="trash" size={18}/></button></div>}{edit && <NoteEditor note={note} onClose={() => setEdit(false)}/ >}{remove && <Modal title="Удалить эту заметку?" onClose={() => setRemove(false)}><p className="detail-description">«{note.title}» будет удалена вместе с доступом приглашённых пользователей.</p><Action className="button-red" onClick={async () => {await api("/notes/"+note.id,"DELETE");refreshData();router.push("/notes");}}>Удалить заметку</Action></Modal>}</>}</div></Shell>;
}
export default function NotePage() { return <Suspense fallback={<Shell><Loading/></Shell>}><NoteContent/></Suspense>; }
