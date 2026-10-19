"use client";

import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import { api, formatDate, refreshData, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { PostComment, ProfilePost } from "@/lib/community";
import { Action, ErrorMessage, Icon, Loading } from "./ui";
import { PostRichText, PostTextEditor } from "./post-rich-text";

export function PostReactions({ post, onOpenComments, onChange }: { post: ProfilePost; onOpenComments?: () => void; onChange: (post: ProfilePost) => void }) {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  async function like() {
    if (!user) { setError("Войди в аккаунт, чтобы поставить лайк."); return; }
    setBusy(true); setError(null);
    try { onChange(await api<ProfilePost>(`/profile/posts/${post.id}/like`, post.liked_by_me ? "DELETE" : "PUT")); refreshData(); }
    catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }
  return <div className="post-reaction-area"><div className="post-reactions"><button type="button" className={"post-reaction " + (post.liked_by_me ? "is-liked" : "")} aria-label={post.liked_by_me ? "Убрать лайк" : "Поставить лайк"} aria-pressed={!!post.liked_by_me} disabled={busy} onClick={()=>{void like();}}><Icon name="heart" size={25}/><span>{post.likes_count ?? 0}</span></button>{onOpenComments ? <button type="button" className="post-reaction" aria-label="Открыть комментарии поста" onClick={onOpenComments}><Icon name="message" size={25}/><span>{post.comments_count ?? 0}</span></button> : <span className="post-reaction"><Icon name="message" size={25}/><span>{post.comments_count ?? 0}</span></span>}</div><ErrorMessage error={error}/></div>;
}

export function PostComments({ postId, onCountChange }: { postId: number; onCountChange: (delta: number) => void }) {
  const { user } = useAuth();
  const result = useApi<PostComment[]>(`/profile/posts/${postId}/comments`);
  const [content, setContent] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null);
  const draftKey = user ? `nen-comment:${user.id}:${postId}` : null;
  useEffect(() => {
    let active = true;
    Promise.resolve().then(() => { try { if (active && draftKey) setContent(localStorage.getItem(draftKey) ?? ""); } catch {} });
    return () => { active = false; };
  }, [draftKey]);
  function change(value: string) { setContent(value); if (draftKey) { try { localStorage.setItem(draftKey, value); } catch {} } }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      await api<PostComment>(`/profile/posts/${postId}/comments`, "POST", { content });
      change(""); onCountChange(1); result.reload(); refreshData();
    } catch (error) { setError((error as Error).message + " Текст комментария сохранён."); }
    finally { setBusy(false); }
  }
  return <section className="post-comments" id={`post-comments-${postId}`}><h3><Icon name="message"/>Комментарии</h3><ErrorMessage error={result.error}/>{result.loading ? <Loading/> : result.data?.length ? <div className="post-comment-list">{result.data.map(comment=><article className="post-comment" key={comment.id}><header><Link href={"/people/"+comment.author.username}>{comment.author.full_name}</Link><time dateTime={comment.created_at}>{formatDate(comment.created_at)}</time>{comment.can_delete && <Action className="button-quiet comment-remove" onClick={async()=>{await api(`/profile/posts/${postId}/comments/${comment.id}`,"DELETE");onCountChange(-1);result.reload();refreshData();}}><Icon name="trash" size={19}/><span>Удалить</span></Action>}</header><PostRichText content={comment.content}/></article>)}</div> : !result.error && <p className="muted">Здесь пока тихо. Начни обсуждение.</p>}
    {user && !result.error ? <form className="post-comment-form form-stack" onSubmit={submit}><PostTextEditor value={content} onChange={change} disabled={busy} maxLength={3000} label="Твой комментарий" placeholder="Поделись мыслями о посте"/><ErrorMessage error={error}/><button className="button" disabled={busy || !content.trim()}>{busy ? "Отправляем…" : "Отправить комментарий"}<Icon name="arrow"/></button></form> : !user && <p className="muted">Войди в аккаунт, чтобы участвовать в обсуждении.</p>}
  </section>;
}

export function PostCommentPreview({post, onOpen}: {post: ProfilePost; onOpen: () => void}) {
  const count = post.comments_count ?? 0;
  const result = useApi<PostComment[]>(count > 0 ? `/profile/posts/${post.id}/comments?limit=3` : null);
  return <section className="feed-comment-preview" aria-label="Комментарии к посту">
    {result.data?.slice(0,3).map(comment => <article className="feed-comment-excerpt" key={comment.id}><Link href={"/people/"+comment.author.username}>{comment.author.full_name}</Link><PostRichText content={comment.content}/></article>)}
    {result.loading && <p className="muted">Загружаем комментарии…</p>}
    {result.error && <p className="muted">Не удалось загрузить комментарии.</p>}
    <button type="button" className="text-link feed-comments-open" onClick={onOpen}><Icon name="message" size={22}/>{count > 3 ? `Все комментарии · ${count}` : count ? "Обсудить пост" : "Написать комментарий"}<Icon name="chevron" size={20}/></button>
  </section>;
}
