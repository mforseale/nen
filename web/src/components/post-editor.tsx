"use client";
/* eslint-disable @next/next/no-img-element -- Local upload previews do not use the shared image optimizer. */

import { useEffect, useRef, useState, type FormEvent } from "react";
import { refreshData } from "@/lib/api";
import { audiences,type ProfileFile,type ProfilePost } from "@/lib/community";
import { fileIcon, fileSize, MAX_FILE_SIZE, MAX_FILES, MAX_POST_SIZE, multipart } from "@/lib/profile-files";
import { ErrorMessage, Icon, Modal } from "./ui";

type Pending = { key: string; file: File; preview: string | null };
export function PostEditor({ post, onClose }: { post?: ProfilePost; onClose: () => void }) {
  const [retained,setRetained] = useState<ProfileFile[]>(post?.attachments ?? []);
  const [pending,setPending] = useState<Pending[]>([]); const [removeImage,setRemoveImage] = useState(false);
  const [error,setError] = useState<string | null>(null); const [busy,setBusy] = useState(false);
  const previews = useRef(new Set<string>());
  useEffect(() => {const urls = previews.current;return () => {urls.forEach(url => URL.revokeObjectURL(url));};},[]);
  function select(files: FileList | null) {
    if (!files) return;
    const selected = Array.from(files).filter(file => !pending.some(item => item.key === `${file.name}:${file.size}:${file.lastModified}`));
    if (retained.length + pending.length + selected.length > MAX_FILES) {setError("В одном посте может быть до 10 файлов.");return;}
    if (selected.some(file => file.size > MAX_FILE_SIZE)) {setError("Один файл должен быть не больше 25 МиБ.");return;}
    if (retained.reduce((sum,file)=>sum+file.size,0) + [...pending.map(item=>item.file),...selected].reduce((sum,file)=>sum+file.size,0) > MAX_POST_SIZE) {setError("Суммарный размер файлов поста — до 50 МиБ.");return;}
    setError(null);setPending([...pending,...selected.map(file => {
      const preview = /^image\/(png|jpeg|webp|gif)$/.test(file.type) ? URL.createObjectURL(file) : null;
      if (preview) previews.current.add(preview);
      return {key:`${file.name}:${file.size}:${file.lastModified}`,file,preview};
    })]);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();const form = new FormData(event.currentTarget);setBusy(true);setError(null);
    const body = new FormData();body.set("payload",JSON.stringify({title:form.get("title"),content:form.get("content"),url:form.get("url"),visibility:form.get("visibility"),keep_ids:retained.map(file=>file.id),pin_new:form.get("pin_new") === "on",remove_image:removeImage}));
    pending.forEach(item=>body.append("files",item.file));
    try {await multipart(post ? `/my/feed/${post.id}` : "/my/feed",post ? "PUT" : "POST",body);refreshData();onClose();}
    catch(error) {setError((error as Error).message);} finally {setBusy(false);}
  }
  return <Modal title={post ? "Изменить пост" : "Новый пост"} onClose={onClose}><form className="form-stack post-composer" onSubmit={submit}>
    <label>Заголовок (необязательно)<input name="title" defaultValue={post?.title} maxLength={150} placeholder="О чём этот пост?"/></label>
    <label>Текст<textarea name="content" defaultValue={post?.content} maxLength={10000} placeholder="Поделись мыслями, впечатлениями или результатом"/></label>
    <label className="file-drop-label"><Icon name="upload"/><strong>Добавить файлы</strong><span>Картинки, музыка, видео, документы — любые форматы</span><input type="file" multiple disabled={busy} onChange={event=>{select(event.target.files);event.target.value="";}}/></label>
    <p className="form-caption">До 10 файлов в посте · 25 МиБ на файл · 50 МиБ суммарно. Музыка появится под картинками.</p>
    {(retained.length > 0 || pending.length > 0) && <div className="composer-attachments">{retained.map(file=><div key={file.id}><Icon name={fileIcon(file.kind)}/><span><strong>{file.name}</strong><small>{fileSize(file.size)}{file.pinned && " · в закрепе"}</small></span><button type="button" className="icon-button" aria-label={"Убрать вложение "+file.name} onClick={()=>setRetained(retained.filter(item=>item.id!==file.id))}><Icon name="close"/></button></div>)}{pending.map(item=><div key={item.key}>{item.preview ? <img src={item.preview} alt=""/> : <Icon name={item.file.type.startsWith("audio/") ? "music" : "file"}/>}<span><strong>{item.file.name}</strong><small>{fileSize(item.file.size)} · новый файл</small></span><button type="button" className="icon-button" aria-label={"Убрать файл "+item.file.name} onClick={()=>{if(item.preview){URL.revokeObjectURL(item.preview);previews.current.delete(item.preview);}setPending(pending.filter(file=>file.key!==item.key));}}><Icon name="close"/></button></div>)}</div>}
    {post?.image_url && !removeImage && <div className="post-image-preview"><img src={post.image_url} alt="Картинка из прежней публикации"/><button type="button" className="text-link" onClick={()=>setRemoveImage(true)}>Убрать прежнюю картинку</button></div>}
    {pending.length > 0 && <label className="composer-pin"><input type="checkbox" name="pin_new"/>Закрепить новые вложения в профиле (до 10 файлов в закрепе)</label>}
    <label>Ссылка (необязательно)<input type="url" name="url" defaultValue={post?.url} maxLength={2000} placeholder="https://…"/></label>
    <label>Кто видит<select name="visibility" defaultValue={post?.visibility ?? "private"}>{Object.entries(audiences).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><ErrorMessage error={error}/><button className="button button-red full-width" disabled={busy}>{busy ? "Публикуем…" : post ? "Сохранить пост" : "Опубликовать"}<Icon name="arrow"/></button>
  </form></Modal>;
}
