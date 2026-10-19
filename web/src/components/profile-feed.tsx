"use client";
/* eslint-disable @next/next/no-img-element -- Private images retain authenticated direct URLs. */

import Link from "next/link";
import { useState } from "react";
import { api, formatDate, refreshData } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { audiences, type ProfilePost } from "@/lib/community";
import { Action, Icon, Modal } from "./ui";
import { PostEditor } from "./post-editor";
import { AttachmentList } from "./profile-files";

export function FeedPost({ post, owner = false }: { post: ProfilePost; owner?: boolean }) {
  const [expanded,setExpanded] = useState(false);
  const [editing,setEditing] = useState(false);
  const [removing,setRemoving] = useState(false);
  const [image,setImage] = useState(false);
  const count = (post.attachments?.length ?? 0) + Number(!!post.image_url);
  return <article className="feed-post uniform-feed-post" data-post-id={post.id}>
    <header>{post.author && <Link className="feed-post-author" href={"/people/"+post.author.username}>{post.author.avatar_url ? <img src={post.author.avatar_url} alt=""/> : <span>{post.author.full_name.slice(0,1)}</span>}<strong>{post.author.full_name}</strong></Link>}<div><time dateTime={post.created_at}>{formatDate(post.created_at)}</time><span className="audience-label"><Icon name={post.visibility === "public" ? "globe" : post.visibility === "friends" ? "friends" : "lock"} size={18}/>{audiences[post.visibility]}</span></div>{owner && <div className="feed-owner-controls"><button className="icon-button" aria-label={"Изменить публикацию «"+post.title+"»"} onClick={()=>setEditing(true)}><Icon name="settings"/></button><button className="icon-button" aria-label={"Удалить публикацию «"+post.title+"»"} onClick={()=>setRemoving(true)}><Icon name="trash"/></button></div>}</header>
    <div className="feed-post-copy">{post.title && <h3>{post.title}</h3>}{post.content && <p className="feed-post-text clamped">{post.content}</p>}</div>
    <div className="feed-post-preview">{post.image_url && <button className="legacy-post-image" aria-label="Открыть картинку" onClick={()=>setImage(true)}><img src={post.image_url} alt={post.title || "Картинка в посте"} loading="lazy"/></button>}<AttachmentList files={post.attachments ?? []} owner={owner} compact/></div>
    <footer className="feed-post-footer"><button className="text-link" onClick={()=>setExpanded(true)}>Открыть пост{count ? ` · ${count} файлов` : ""}<Icon name="arrow"/></button>{post.url && <a className="feed-post-link" href={post.url} target="_blank" rel="noopener noreferrer"><Icon name="link"/>Ссылка</a>}</footer>
    {expanded && <Modal title={post.title || "Пост"} onClose={()=>setExpanded(false)} className="profile-detail-dialog post-detail-dialog"><div className="post-detail-content"><p className="feed-post-text">{post.content}</p>{post.image_url && <img className="inspector-image" src={post.image_url} alt={post.title || "Картинка в посте"}/>}<AttachmentList files={post.attachments ?? []} owner={owner}/>{post.url && <a className="feed-post-link" href={post.url} target="_blank" rel="noopener noreferrer"><Icon name="link"/>Открыть ссылку <Icon name="arrow"/></a>}</div></Modal>}
    {editing && <PostEditor post={post} onClose={()=>setEditing(false)}/>}
    {removing && <Modal title="Удалить пост?" onClose={()=>setRemoving(false)}><p className="muted">Пост и все его вложения будут удалены, в том числе из закрепа.</p><Action className="button-red full-width" onClick={async()=>{await api(`/my/posts/${post.id}`,"DELETE");setRemoving(false);refreshData();}}>Удалить пост</Action></Modal>}
    {image && <Modal title={post.title || "Картинка"} onClose={()=>setImage(false)} className="profile-detail-dialog"><img className="inspector-image" src={post.image_url!} alt={post.title}/></Modal>}
  </article>;
}

export function ProfilePosts({ posts, owner = false, forum = false, title }: { posts: ProfilePost[]; owner?: boolean; forum?: boolean; title?:string }) {
  const {user} = useAuth();
  const [create,setCreate] = useState(false);
  const [limit,setLimit] = useState(forum ? 10 : 4);
  return <section className={"profile-feed"+(forum ? " forum-post-stream" : "")}><div className="feed-heading"><div><h2>{title ?? (forum ? "Посты пользователей" : "Лента")}</h2><p>{forum ? "Публикации, доступные тебе по настройкам их авторов." : "Посты, картинки и музыка в одном месте."}</p></div>{(owner || forum && user) && <button className="button" onClick={()=>setCreate(true)}><Icon name="plus"/>Написать пост</button>}</div>
    {posts.length ? <div className="feed-posts">{posts.slice(0,limit).map(post=><FeedPost key={post.id} post={post} owner={owner || forum && post.author?.id === user?.id}/>)}</div> : <p className="profile-empty-line">{owner ? "Напиши первый пост или добавь картинки и музыку." : "Нет доступных публикаций."}</p>}
    {posts.length > limit && <button className="button button-quiet feed-more" onClick={()=>setLimit(limit+(forum ? 10 : 4))}>Показать ещё посты <Icon name="chevron"/></button>}
    {create && <PostEditor onClose={()=>setCreate(false)}/>}
  </section>;
}
