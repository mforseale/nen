"use client";
/* eslint-disable @next/next/no-img-element -- Private images retain authenticated direct URLs. */

import Link from "next/link";
import { useRef, useState } from "react";
import { api, formatDate, refreshData, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { audiences, type ProfilePost } from "@/lib/community";
import { safePostUrl } from "@/lib/post-rich-text";
import { Action, ErrorMessage, Icon, Loading, Modal } from "./ui";
import { PostEditor } from "./post-editor";
import { AttachmentList } from "./profile-files";
import { PostRichText } from "./post-rich-text";
import { PostCommentPreview, PostComments, PostReactions } from "./post-interactions";

function PostDetail({ postId, owner, title, onClose, onChange, commentsFirst }: { postId: number; owner: boolean; title: string; onClose: () => void; onChange: (post: ProfilePost) => void; commentsFirst: boolean }) {
  const detail = useApi<ProfilePost>(`/profile/posts/${postId}`);
  const [updated, setUpdated] = useState<{ source: ProfilePost | null; post: ProfilePost } | null>(null);
  const post = updated?.source === detail.data ? updated.post : detail.data;
  const comments = useRef<HTMLDivElement>(null);
  const scrolledToComments = useRef(false);
  function change(value: ProfilePost) { setUpdated({source:detail.data,post:value}); onChange(value); }
  const href = post?.url ? safePostUrl(post.url) : null;
  return <Modal title={post?.title || title || "Пост"} onClose={onClose} className="profile-detail-dialog post-detail-dialog"><ErrorMessage error={detail.error}/>{detail.loading ? <Loading/> : !detail.error && post && <div className="post-detail-content">
    <div className="post-detail-meta"><time dateTime={post.created_at}>{formatDate(post.created_at)}</time><span className="audience-label"><Icon name={post.visibility === "public" ? "globe" : post.visibility === "friends" ? "friends" : "lock"} size={19}/>{audiences[post.visibility]}</span></div>
    <AttachmentList files={post.attachments ?? []} owner={owner} legacyImage={post.image_url ? {url:post.image_url,title:post.title} : undefined}/>
    {post.content && <PostRichText content={post.content}/>}
    {href && <a className="post-link-card" href={href} target="_blank" rel="noopener noreferrer"><span className="post-file-emblem"><Icon name="link" size={27}/></span><span><strong>Открыть ссылку</strong><small>{new URL(href).hostname}</small></span><Icon name="arrow"/></a>}
    <PostReactions post={post} onChange={change} onOpenComments={()=>comments.current?.scrollIntoView({behavior:"smooth",block:"start"})}/>
    <div ref={element=>{comments.current=element;if(element && commentsFirst && !scrolledToComments.current){scrolledToComments.current=true;requestAnimationFrame(()=>element.scrollIntoView({block:"start"}));}}}><PostComments postId={post.id} onCountChange={delta=>change({...post,comments_count:Math.max(0,(post.comments_count ?? 0)+delta)})}/></div>
  </div>}</Modal>;
}

export function FeedPost({ post: original, owner = false }: { post: ProfilePost; owner?: boolean }) {
  const [expanded,setExpanded] = useState(false);
  const [editing,setEditing] = useState(false), [removing,setRemoving] = useState(false), [updated,setUpdated] = useState<{source:ProfilePost;post:ProfilePost}|null>(null);
  const post = updated?.source === original ? updated.post : original;
  const count = (post.attachments?.length ?? 0) + Number(!!post.image_url);
  function openComments() { setExpanded(true); }
  function change(value: ProfilePost) { setUpdated({source:original,post:value}); }
  const href = post.url ? safePostUrl(post.url) : null;
  return <article className={"feed-post uniform-feed-post"+(!count ? " text-only-post" : "")} data-post-id={post.id}>
    <header>{post.author && <Link className="feed-post-author" href={"/people/"+post.author.username}>{post.author.avatar_url ? <img src={post.author.avatar_url} alt=""/> : <span>{post.author.full_name.slice(0,1)}</span>}<strong>{post.author.full_name}</strong></Link>}<div className="feed-post-meta"><time dateTime={post.created_at}>{formatDate(post.created_at)}</time><span className="audience-label"><Icon name={post.visibility === "public" ? "globe" : post.visibility === "friends" ? "friends" : "lock"} size={18}/>{audiences[post.visibility]}</span></div>{owner && <div className="feed-owner-controls"><button className="icon-button" aria-label={"Изменить публикацию «"+post.title+"»"} onClick={()=>setEditing(true)}><Icon name="settings"/></button><button className="icon-button" aria-label={"Удалить публикацию «"+post.title+"»"} onClick={()=>setRemoving(true)}><Icon name="trash"/></button></div>}</header>
    <div className="feed-post-copy">{post.title && <h3>{post.title}</h3>}{post.content && <PostRichText content={post.content} className="feed-post-text"/>}</div>
    {count > 0 && <div className="feed-post-preview"><AttachmentList files={post.attachments ?? []} owner={owner} compact legacyImage={post.image_url ? {url:post.image_url,title:post.title} : undefined}/></div>}
    {href && <a className="post-link-card" href={href} target="_blank" rel="noopener noreferrer"><span className="post-file-emblem"><Icon name="link" size={24}/></span><span><strong>Открыть ссылку</strong><small>{new URL(href).hostname}</small></span><Icon name="arrow"/></a>}
    <footer className="feed-post-footer"><PostReactions post={post} onChange={change} onOpenComments={openComments}/></footer>
    <PostCommentPreview post={post} onOpen={openComments}/>
    {expanded && <PostDetail postId={post.id} title={post.title} owner={owner} onClose={()=>setExpanded(false)} onChange={change} commentsFirst/>}
    {editing && <PostEditor post={original} onClose={()=>setEditing(false)}/>}
    {removing && <Modal title="Удалить пост?" onClose={()=>setRemoving(false)}><p className="muted">Пост и все его вложения будут удалены, в том числе из закрепа.</p><Action className="button-red full-width" onClick={async()=>{await api(`/my/posts/${post.id}`,"DELETE");setRemoving(false);refreshData();}}>Удалить пост</Action></Modal>}
  </article>;
}

export function ProfilePosts({ posts, owner = false, forum = false, title }: { posts: ProfilePost[]; owner?: boolean; forum?: boolean; title?:string }) {
  const {user} = useAuth();
  const [create,setCreate] = useState(false), [limit,setLimit] = useState(forum ? 10 : 4);
  return <section className={"profile-feed"+(forum ? " forum-post-stream" : "")}><div className="feed-heading"><div><h2>{title ?? (forum ? "Посты пользователей" : "Лента")}</h2><p>{forum ? "Публикации, доступные тебе по настройкам их авторов." : "Посты, картинки и музыка в одном месте."}</p></div>{(owner || forum && user) && <button className="button" onClick={()=>setCreate(true)}><Icon name="plus"/>Написать пост</button>}</div>
    {posts.length ? <div className="feed-posts">{posts.slice(0,limit).map(post=><FeedPost key={post.id} post={post} owner={owner || forum && post.author?.id === user?.id}/>)}</div> : <p className="profile-empty-line">{owner ? "Напиши первый пост или добавь картинки и музыку." : "Нет доступных публикаций."}</p>}
    {posts.length > limit && <button className="button button-quiet feed-more" onClick={()=>setLimit(limit+(forum ? 10 : 4))}>Показать ещё посты <Icon name="chevron"/></button>}
    {create && <PostEditor onClose={()=>setCreate(false)}/>}
  </section>;
}
