"use client";
/* eslint-disable @next/next/no-img-element -- Authenticated file previews must use the current browser session. */

import { useState, type FormEvent } from "react";
import { api, refreshData, useApi } from "@/lib/api";
import { audiences, type ProfileFile } from "@/lib/community";
import { fileExtension, fileIcon, fileSize, MAX_FILE_SIZE, multipart } from "@/lib/profile-files";
import { Action, ErrorMessage, Icon, Loading, Modal } from "./ui";
import { PostGallery } from "./post-gallery";

export function PinButton({ file }: { file: ProfileFile }) {
  return <Action className={"button-quiet file-pin " + (file.pinned ? "pinned" : "")} onClick={async()=>{await api(`/my/files/${file.id}`,"PUT",{pinned:!file.pinned});refreshData();}}><Icon name="pin" size={19}/>{file.pinned ? "В закрепе" : "Закрепить"}</Action>;
}

export function FileInspector({ file: original, owner, onClose }: { file: ProfileFile; owner: boolean; onClose: () => void }) {
  const [file,setFile] = useState(original); const [remove,setRemove] = useState(false); const [error,setError] = useState<string|null>(null);const [busy,setBusy] = useState(false);
  async function visibility(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();setBusy(true);setError(null);
    try {setFile(await api<ProfileFile>(`/my/files/${file.id}`,"PUT",{pinned:file.pinned,visibility:new FormData(event.currentTarget).get("visibility")}));refreshData();}
    catch(error){setError((error as Error).message);} finally {setBusy(false);}
  }
  return <Modal title={file.name} onClose={onClose} className="profile-detail-dialog"><div className="file-inspector">
    {file.kind === "image" ? <img className="inspector-image" src={file.url} alt={file.name}/> : file.kind === "audio" ? <audio controls preload="none" src={file.url}>Скачать аудио можно по ссылке ниже.</audio> : file.kind === "video" ? <video controls preload="metadata" src={file.url}/> : <div className="file-document-art"><Icon name="file" size={60}/><strong>{fileExtension(file.name)}</strong></div>}
    <p className="file-inspector-meta">{fileSize(file.size)} · {file.media_type} · {audiences[file.visibility]}{file.post_id && " · вложение поста"}</p>
    <div className="file-inspector-actions"><a className="button" href={file.download_url}><Icon name="download"/>Скачать файл</a>{owner && <Action className="button-quiet" onClick={async()=>{setFile(await api<ProfileFile>(`/my/files/${file.id}`,"PUT",{pinned:!file.pinned}));refreshData();}}><Icon name="pin"/>{file.pinned ? "Снять закреп" : "Закрепить"}</Action>}</div>
    {owner && !file.post_id && <form className="file-visibility-form" onSubmit={visibility}><label>Кто видит файл<select name="visibility" defaultValue={file.visibility}>{Object.entries(audiences).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><button className="button button-quiet" disabled={busy}>Сохранить видимость</button><ErrorMessage error={error}/></form>}
    {owner && file.post_id && <p className="muted">Видимость этого файла меняется вместе с постом.</p>}
    {owner && <div className="file-delete-area">{remove ? <><p>Удалить файл{file.post_id ? " из поста и закрепа" : " из библиотеки"}?</p><Action className="button-red" onClick={async()=>{await api(`/my/files/${file.id}`,"DELETE");refreshData();onClose();}}>Удалить файл</Action><button onClick={()=>setRemove(false)} className="text-link">Оставить</button></> : <button className="text-link" onClick={()=>setRemove(true)}><Icon name="trash" size={19}/>Удалить файл</button>}</div>}
  </div></Modal>;
}

function PostImageViewer({images, index, onChange, onClose}: {images: {url: string; downloadUrl: string}[]; index: number; onChange: (index: number) => void; onClose: () => void}) {
  const image = images[index];
  return <Modal title="Просмотр изображения" onClose={onClose} className="post-image-dialog"><div className="post-image-frame"><img src={image.url} alt={"Изображение " + (index + 1)}/></div><div className="post-image-controls">{images.length > 1 && <button type="button" className="icon-button image-previous" aria-label="Предыдущее изображение" onClick={()=>onChange((index+images.length-1)%images.length)}><Icon name="chevron"/></button>}<span aria-live="polite">{index + 1} / {images.length}</span>{images.length > 1 && <button type="button" className="icon-button" aria-label="Следующее изображение" onClick={()=>onChange((index+1)%images.length)}><Icon name="chevron"/></button>}<a className="text-link" href={image.downloadUrl}><Icon name="download" size={22}/>Оригинал</a></div></Modal>;
}

export function AttachmentList({ files, owner = false, compact = false, legacyImage }: { files: ProfileFile[]; owner?: boolean; compact?: boolean; legacyImage?: { url: string; title: string } }) {
  const [view,setView] = useState<ProfileFile|null>(null), [imageIndex,setImageIndex] = useState<number|null>(null);
  const images = [...(legacyImage ? [{ url: legacyImage.url, name: legacyImage.title || "Изображение в посте", file: null as ProfileFile | null }] : []), ...files.filter(file=>file.kind === "image").map(file=>({ url:file.url,name:file.name,file }))];
  const media = files.filter(file=>file.kind === "audio" || file.kind === "video"), other = files.filter(file=>file.kind === "file");
  return <div className={"post-attachments"+(compact ? " compact-attachments" : "")}>
    {images.length > 0 && <PostGallery images={images} compact={compact} onOpen={setImageIndex}/>}
    {media.length > 0 && <div className="post-media-list">{media.map(file=><div className={"post-media post-media-"+file.kind} key={file.id}><div className="post-media-heading"><span className="post-file-emblem"><Icon name={fileIcon(file.kind)}/></span><strong>{file.name}</strong>{owner && !compact && <PinButton file={file}/>}</div>{file.kind === "audio" ? <audio controls preload="none" src={file.url}/> : <video controls preload="metadata" src={file.url}/>}<div className="post-media-footer"><span>{fileSize(file.size)}</span><a href={file.download_url}>Скачать</a></div></div>)}</div>}
    {other.length > 0 && <div className="post-other-files">{other.map(file=><div key={file.id}><button className="post-file-open" onClick={()=>setView(file)}><span className="post-file-emblem"><Icon name="file"/><b>{fileExtension(file.name)}</b></span><span><strong>{file.name}</strong><small>{fileSize(file.size)}</small></span></button>{owner && !compact && <PinButton file={file}/>}<a className="icon-button" href={file.download_url} aria-label={"Скачать "+file.name}><Icon name="download"/></a></div>)}</div>}
    {view && <FileInspector key={view.id} file={view} owner={owner} onClose={()=>setView(null)}/>}
    {imageIndex !== null && images.length > 0 && <PostImageViewer images={images.map(image=>({url:image.url,downloadUrl:image.file?.download_url ?? image.url}))} index={Math.min(imageIndex,images.length-1)} onChange={setImageIndex} onClose={()=>setImageIndex(null)}/>}
  </div>;
}

function FileTile({ file, onClick }: { file: ProfileFile; onClick: () => void }) {
  return <button className={"pinned-file-tile file-kind-"+file.kind} onClick={onClick}><span className="pinned-file-art">{file.kind === "image" ? <img src={file.url} alt="" loading="lazy"/> : <><Icon name={fileIcon(file.kind)} size={32}/><b>{file.kind === "audio" ? "АУДИО" : file.kind === "video" ? "ВИДЕО" : fileExtension(file.name)}</b></>}</span><strong>{file.name}</strong><small>{fileSize(file.size)}</small></button>;
}

function FileLibrary({ pins, owner, onClose }: { pins: ProfileFile[]; owner: boolean; onClose: () => void }) {
  const library = useApi<ProfileFile[]>(owner ? "/my/files" : null);
  const [view,setView] = useState<ProfileFile|null>(null); const [error,setError] = useState<string|null>(null); const [busy,setBusy] = useState(false); const [limit,setLimit] = useState(12);
  const items = owner ? library.data ?? [] : pins;
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();const form=event.currentTarget;const body=new FormData(form);const file=body.get("file") as File;
    if(file.size>MAX_FILE_SIZE){setError("Один файл должен быть не больше 25 МиБ.");return;}
    setBusy(true);setError(null);try{await multipart("/my/files","POST",body);form.reset();refreshData();}catch(error){setError((error as Error).message);}finally{setBusy(false);}
  }
  return <Modal title={owner ? "Файлы профиля" : "Закреплённые файлы"} onClose={onClose} className="profile-detail-dialog">
    <p className="muted">В закрепе {owner ? items.filter(file=>file.pinned).length : pins.length} из 10 файлов.{owner && " Снятые закрепы остаются в твоей библиотеке."}</p>
    {owner && <form className="library-upload form-stack" onSubmit={upload}><label>Добавить файл в закреп<input name="file" type="file" required disabled={busy}/></label><label>Кто видит<select name="visibility" defaultValue="private">{Object.entries(audiences).map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><button className="button" disabled={busy || items.filter(file=>file.pinned).length >= 10}>{busy ? "Загружаем…" : "Загрузить и закрепить"}<Icon name="upload"/></button><p className="form-caption">Любой формат · до 25 МиБ на файл</p></form>}
    <ErrorMessage error={error ?? library.error}/>{owner && library.loading ? <Loading/> : <div className="file-library-list">{items.slice(0,limit).map(file=><div key={file.id}><button onClick={()=>setView(file)}><Icon name={fileIcon(file.kind)}/><span><strong>{file.name}</strong><small>{fileSize(file.size)} · {audiences[file.visibility]}</small></span></button>{owner && <PinButton file={file}/>}</div>)}</div>}
    {items.length > limit && <button className="button button-quiet" onClick={()=>setLimit(limit+12)}>Показать ещё</button>}
    {!items.length && !library.loading && <p className="profile-empty-line">Файлов пока нет.</p>}
    {view && <FileInspector key={view.id} file={view} owner={owner} onClose={()=>setView(null)}/>}
  </Modal>;
}

export function PinnedFiles({ files, owner = false, compact = false }: { files: ProfileFile[]; owner?: boolean; compact?: boolean }) {
  const [view,setView] = useState<ProfileFile|null>(null); const [library,setLibrary] = useState(false);
  return <section className="profile-showcase pinned-showcase"><div className="showcase-heading"><button onClick={()=>setLibrary(true)}><Icon name="pin"/><h2>Закреплённые файлы</h2><span>{files.length}/10</span><Icon name="chevron"/></button>{owner && <button className="icon-button" onClick={()=>setLibrary(true)} aria-label="Добавить или настроить закреплённые файлы"><Icon name="plus"/></button>}</div>
    {files.length ? <div className="pinned-file-grid">{files.slice(0,compact?4:10).map(file=><FileTile key={file.id} file={file} onClick={()=>setView(file)}/>)}</div> : <p className="showcase-empty">{owner ? "Сохрани здесь до 10 важных файлов любого типа." : "Нет доступных закреплённых файлов."}</p>}
    {(files.length > 4 && compact) && <button className="showcase-more" onClick={()=>setLibrary(true)}>Все файлы <Icon name="arrow"/></button>}
    {library && <FileLibrary pins={files} owner={owner} onClose={()=>setLibrary(false)}/>}{view && <FileInspector key={view.id} file={view} owner={owner} onClose={()=>setView(null)}/>}
  </section>;
}
