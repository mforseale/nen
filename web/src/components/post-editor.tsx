"use client";
/* eslint-disable @next/next/no-img-element -- Local upload previews do not use the shared image optimizer. */

import { memo, useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { refreshData } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { audiences, type Audience, type ProfileFile, type ProfilePost } from "@/lib/community";
import { fileIcon, fileSize, MAX_FILE_SIZE, MAX_FILES, MAX_POST_SIZE, multipart } from "@/lib/profile-files";
import { checkpointPostDraft, deletePostDraft, loadPostDraft, postDraftKey, savePostDraft, type PostDraft } from "@/lib/post-drafts";
import { filePreview } from "@/lib/file-preview";
import { ErrorMessage, Icon, Modal } from "./ui";
import { PostTextEditor } from "./post-rich-text";

type Pending = { key: string; file: File };
const PendingAttachment = memo(function PendingAttachment({ item, onRemove }: { item: Pending; onRemove: (key: string) => void }) {
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    let active = true, url: string | null = null;
    void filePreview(item.file).then(blob => {
      if (!active || !blob) return;
      url = URL.createObjectURL(blob); setPreview(url);
    });
    return () => { active = false; if (url) URL.revokeObjectURL(url); };
  }, [item.file]);
  return <div>{preview ? <img src={preview} alt="" decoding="async"/> : <Icon name={item.file.type.startsWith("audio/") ? "music" : item.file.type.startsWith("image/") ? "image" : "file"}/>}<span><strong>{item.file.name}</strong><small>{fileSize(item.file.size)} · новый файл</small></span><button type="button" className="icon-button" aria-label={"Убрать файл "+item.file.name} onClick={()=>onRemove(item.key)}><Icon name="close"/></button></div>;
});
export function PostEditor({ post: initialPost, onClose }: { post?: ProfilePost; onClose: () => void }) {
  // A background feed refresh must never reset an editor that is already open.
  const [post] = useState(initialPost);
  const { user } = useAuth();
  const key = user ? postDraftKey(user.id, post?.id) : null;
  const [title, setTitle] = useState(post?.title ?? ""), [content, setContent] = useState(post?.content ?? ""), [url, setUrl] = useState(post?.url ?? "");
  const [visibility, setVisibility] = useState<Audience>(post?.visibility ?? "private");
  const [retained, setRetained] = useState<ProfileFile[]>(post?.attachments ?? []);
  const [files, setFiles] = useState<File[]>([]), [removeImage, setRemoveImage] = useState(false), [pinNew, setPinNew] = useState(false);
  const pending = useMemo<Pending[]>(() => files.map(file => ({ key: `${file.name}:${file.size}:${file.lastModified}`, file })), [files]);
  const [error, setError] = useState<string | null>(null), [busy, setBusy] = useState(false), [readyKey, setReadyKey] = useState<string | null>(null);
  const ready = !!key && readyKey === key;
  const [draftMessage, setDraftMessage] = useState("Восстанавливаем черновик…"), [draftError, setDraftError] = useState<string | null>(null);
  const picker = useRef<HTMLInputElement>(null), published = useRef(false), previousFiles = useRef<File[] | null>(null);
  const removePending = useCallback((key: string) => setFiles(items => items.filter(file => `${file.name}:${file.size}:${file.lastModified}` !== key)), []);
  useEffect(() => {
    let active = true;
    if (!key) return;
    loadPostDraft(key).then(draft => {
      if (!active) return;
      if (draft?.version === 1) {
        setTitle(draft.title); setContent(draft.content); setUrl(draft.url); setVisibility(draft.visibility);
        setRetained((post?.attachments ?? []).filter(file => draft.retainedIds.includes(file.id)));
        setRemoveImage(draft.removeImage); setPinNew(draft.pinNew);
        setFiles(draft.files);
        setDraftMessage(draft.missingFiles ? "Восстановлен текст черновика. Браузер не сохранил файлы — прикрепи их повторно." : "Черновик восстановлен — включая прикреплённые файлы.");
      } else setDraftMessage("Черновик сохраняется на этом устройстве.");
      setReadyKey(key);
    }).catch(() => { if (active) { setReadyKey(key); setDraftError("Не удалось открыть черновик. Сохранение браузером может быть ограничено."); } });
    return () => { active = false; };
  }, [key, post]);
  const snapshot = useCallback((): PostDraft => ({ version: 1, updatedAt: Date.now(), title, content, url, visibility, retainedIds: retained.map(file => file.id), files, removeImage, pinNew }), [title, content, url, visibility, retained, files, removeImage, pinNew]);
  useEffect(() => {
    if (!ready || !key || published.current) return;
    let active = true;
    const draft = snapshot(), filesChanged = previousFiles.current !== draft.files;
    previousFiles.current = draft.files;
    // The latest text survives reload immediately. File bytes are written only
    // when attachments change; typing batches small metadata writes after a pause.
    try { checkpointPostDraft(key, draft); } catch {}
    const save = () => {
      if (published.current) return;
      void savePostDraft(key, draft).then(() => { if (active) setDraftError(null); }).catch(error => { if (active) setDraftError((error as Error).message); });
    };
    let timer: number | undefined;
    if (filesChanged) save();
    else timer = window.setTimeout(save, 450);
    window.addEventListener("pagehide", save);
    return () => { active = false; window.clearTimeout(timer); window.removeEventListener("pagehide", save); };
  }, [key, ready, snapshot]);
  async function close() {
    if (busy) return;
    if (key && ready && !published.current) {
      try { await savePostDraft(key, snapshot()); }
      catch (error) { setDraftError((error as Error).message); setError("Редактор оставлен открытым, чтобы сохранить твои файлы. Опубликуй пост или освободи место в браузере."); return; }
    }
    onClose();
  }
  function select(selection: FileList | null) {
    if (!selection) return;
    const selected = Array.from(selection).filter(file => !pending.some(item => item.key === `${file.name}:${file.size}:${file.lastModified}`));
    if (retained.length + pending.length + selected.length + Number(!!post?.image_url && !removeImage) > MAX_FILES) { setError("В одном посте может быть до 10 файлов."); return; }
    if (selected.some(file => file.size > MAX_FILE_SIZE)) { setError("Один файл должен быть не больше 25 МиБ."); return; }
    if (retained.reduce((sum, file) => sum + file.size, 0) + [...pending.map(item => item.file), ...selected].reduce((sum, file) => sum + file.size, 0) > MAX_POST_SIZE) { setError("Суммарный размер файлов поста — до 50 МиБ."); return; }
    setError(null); setFiles([...files, ...selected]);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    if (key) await savePostDraft(key, snapshot()).catch(error => setDraftError((error as Error).message));
    const body = new FormData();
    body.set("payload", JSON.stringify({ title, content, url, visibility, keep_ids: retained.map(file => file.id), pin_new: pinNew, remove_image: removeImage }));
    pending.forEach(item => body.append("files", item.file));
    try {
      await multipart(post ? `/my/feed/${post.id}` : "/my/feed", post ? "PUT" : "POST", body);
    } catch (error) { setError((error as Error).message + " Черновик остаётся в редакторе."); setBusy(false); return; }
    // A successful response remains successful if the browser cannot clean its draft.
    published.current = true;
    if (key) await deletePostDraft(key).catch(() => {});
    setBusy(false); refreshData(); onClose();
  }
  return <Modal title={post ? "Изменить пост" : "Новый пост"} onClose={()=>{void close();}} className="post-editor-dialog"><form className="form-stack post-composer" onSubmit={submit}>
    <div className="post-draft-status" role="status"><Icon name={draftError ? "clock" : "check"} size={19}/><span>{draftError || draftMessage}</span></div>
    <fieldset disabled={busy || !ready} className="post-composer-fields">
      <label>Заголовок (необязательно)<input name="title" value={title} onChange={event=>setTitle(event.target.value)} maxLength={150} placeholder="О чём этот пост?"/></label>
      <PostTextEditor value={content} onChange={setContent} disabled={busy || !ready} onAttach={()=>picker.current?.click()}/>
      <label className="file-drop-label"><Icon name="upload"/><strong>Добавить файлы</strong><span>Изображения, музыка, видео и документы</span><input ref={picker} type="file" multiple disabled={busy || !ready} onChange={event=>{select(event.target.files);event.target.value="";}}/></label>
      <p className="form-caption">До 10 файлов · 25 МиБ на файл · 50 МиБ на пост. Музыка появится под изображениями.</p>
      {(retained.length > 0 || pending.length > 0) && <div className="composer-attachments">{retained.map(file=><div key={file.id}><Icon name={fileIcon(file.kind)}/><span><strong>{file.name}</strong><small>{fileSize(file.size)}{file.pinned && " · в закрепе"}</small></span><button type="button" className="icon-button" aria-label={"Убрать вложение "+file.name} onClick={()=>setRetained(retained.filter(item=>item.id!==file.id))}><Icon name="close"/></button></div>)}{pending.map(item=><PendingAttachment key={item.key} item={item} onRemove={removePending}/>)}</div>}
      {post?.image_url && !removeImage && <div className="post-image-preview"><img src={post.image_url} alt="Картинка из прежней публикации"/><button type="button" className="text-link" onClick={()=>setRemoveImage(true)}>Убрать прежнюю картинку</button></div>}
      {pending.length > 0 && <label className="composer-pin"><input type="checkbox" checked={pinNew} onChange={event=>setPinNew(event.target.checked)}/>Закрепить новые вложения в профиле (до 10 файлов)</label>}
      <label>Ссылка (необязательно)<input type="url" name="url" value={url} onChange={event=>setUrl(event.target.value)} maxLength={2000} placeholder="https://…"/></label>
      <label>Кто видит<select name="visibility" value={visibility} onChange={event=>setVisibility(event.target.value as Audience)}>{Object.entries(audiences).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label>
    </fieldset>
    <ErrorMessage error={error}/><button className="button button-red full-width" disabled={busy || !ready}>{busy ? "Публикуем…" : post ? "Сохранить пост" : "Опубликовать"}<Icon name="arrow"/></button>
    <button type="button" className="text-link draft-close" disabled={busy} onClick={()=>{void close();}}>Закрыть и оставить черновик</button>
    <button type="button" className="text-link draft-close draft-discard" disabled={busy || !ready} onClick={async()=>{published.current=true;if(key)await deletePostDraft(key);onClose();}}>Удалить черновик</button>
  </form></Modal>;
}
