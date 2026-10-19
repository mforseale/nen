"use client";
import Link from "next/link";
import { Suspense, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { api, formatDate, refreshData, useApi, type Forum, type ForumTopic, type Pact } from "@/lib/api";
import { Empty, ErrorMessage, Icon, Loading, PageTitle, Shell } from "@/components/ui";
import { ProfilePosts } from "@/components/profile-feed";
import type { ProfilePost } from "@/lib/community";
import { ActivityFilters, activityScopes, type ActivityScope } from "@/components/activity-filters";

function topicKey(topic: Pick<ForumTopic,"pact_id" | "template_id">) {return topic.pact_id ? `pact:${topic.pact_id}` : `archive:${topic.template_id}`;}
function PactForum({scope}: {scope:ActivityScope}) {
  const params = useSearchParams();
  const {user} = useAuth();
  const [topic,setTopic] = useState<string | null>(null);
  const current = topic ?? (params.get("pact") ? "pact:"+params.get("pact") : params.get("topic") ? "archive:"+params.get("topic") : "");
  const pactId = current.startsWith("pact:") ? current.slice(5) : null;
  const archived = current.startsWith("archive:");
  const suffix = pactId ? "?pact_id="+encodeURIComponent(pactId) : archived ? "?template_id="+encodeURIComponent(current.slice(8)) : "";
  const {data,loading,error} = useApi<Forum>("/forum"+suffix+(suffix ? "&" : "?")+"scope="+scope+"&viewer="+(user?.id ?? "guest"));
  const {data:pact} = useApi<Pact>(pactId && user ? "/pacts/"+pactId : null);
  const [text,setText] = useState("");
  const [composeTopic,setComposeTopic] = useState("");
  const [busy,setBusy] = useState(false);
  const [postError,setPostError] = useState<string | null>(null);
  const ownTopics = data?.topics.filter(item => item.pact_id) ?? [];
  const title = data?.topics.find(item => topicKey(item) === current)?.title ?? pact?.title;
  async function post(event: FormEvent) {
    event.preventDefault();setBusy(true);setPostError(null);
    try {await api("/forum","POST",{content:text,pact_id:Number(pactId ?? composeTopic)});setText("");refreshData();}
    catch(error) {setPostError((error as Error).message);} finally {setBusy(false);}
  }
  return <><PageTitle title={title ?? "Форум"}/><p className="page-intro">{archived ? "Архив публичного обсуждения. Новые сообщения к готовым пактам отключены." : "Обсуждения твоих пактов доступны только их участникам."}</p>
    {!current && <section className="trending-section"><div className="section-heading"><span className="eyebrow"><Icon name="flame"/>СЕЙЧАС ОБСУЖДАЮТ</span><span className="muted text-small">Последние 7 дней</span></div>{data?.trending.length ? <div className="trending-grid">{data.trending.map((item,index) => <button key={topicKey(item)} onClick={() => setTopic(topicKey(item))}><span className="trend-number">{String(index+1).padStart(2,"0")}</span><div><h3>{item.title}</h3><p>{item.count} сообщений{item.template_id ? " · архив" : ""}</p></div><Icon name="arrow"/></button>)}</div> : <p className="trending-empty">Пока нет обсуждений за последние 7 дней.</p>}</section>}
    <div className="forum-layout"><div><div className="section-heading"><h2 className="section-label">{pactId ? "Разговор участников" : archived ? "Архив" : "Последние сообщения"}</h2><select aria-label="Фильтр обсуждений" value={current} onChange={event => setTopic(event.target.value)}><option value="">Все обсуждения</option>{data?.topics.map(item => <option value={topicKey(item)} key={topicKey(item)}>{item.title}{item.template_id ? " · архив" : ""}</option>)}</select></div><ErrorMessage error={error}/>{loading ? <Loading/> : data?.comments.length ? <div className="forum-feed">{data.comments.map(comment => <article key={comment.id} className="forum-post"><Link href={"/people/"+comment.author.username} className="post-avatar">{comment.author.full_name.slice(0,1)}</Link><div><div className="post-meta"><Link href={"/people/"+comment.author.username}>{comment.author.full_name}</Link><span>@{comment.author.username}</span><time>{formatDate(comment.created_at)}</time></div>{!current && <button className="post-topic" onClick={() => setTopic(topicKey(comment))}><Icon name={comment.template_id ? "book" : "lock"} size={20}/>{comment.topic_title}{comment.template_id ? " · архив" : ""}</button>}<p>{comment.content}</p></div></article>)}</div> : !error && <Empty title="Сообщений пока нет"><p>{archived ? "В этой архивной теме нет сообщений." : "Выбери свой пакт и напиши первое сообщение."}</p></Empty>}</div>
      <aside className="forum-compose"><h2>{archived ? "Архив обсуждения" : "Новое сообщение"}</h2>{archived ? <><p className="muted">История сохранена для чтения.</p><button className="button full-width" onClick={() => setTopic("")}>К обсуждениям <Icon name="arrow"/></button></> : !user ? <Link href="/login" className="button">Войти и написать <Icon name="arrow"/></Link> : error ? <p className="muted">Выбери доступное обсуждение.</p> : !loading && !pactId && !ownTopics.length ? <><p className="muted">Создай свой пакт, чтобы вести его обсуждение.</p><Link href="/" className="button">Создать свой пакт <Icon name="plus"/></Link></> : <form className="form-stack" onSubmit={post}>{!pactId && <label>Твой пакт<select required value={composeTopic} onChange={event => setComposeTopic(event.target.value)}><option value="">Выбери пакт</option>{ownTopics.map(item => <option value={item.pact_id!} key={item.pact_id}>{item.title}</option>)}</select></label>}<p className="form-caption"><Icon name="lock" size={19}/>Только для участников выбранного пакта.</p><label className="sr-only" htmlFor="forum-message">Сообщение</label><textarea id="forum-message" placeholder="Текст сообщения…" required maxLength={3000} value={text} onChange={event => setText(event.target.value)}/><ErrorMessage error={postError}/><button className="button full-width" disabled={loading || busy || !text.trim() || !pactId && !composeTopic}>{busy ? "Отправляем…" : "Отправить"}<Icon name="arrow"/></button></form>}</aside>
    </div>
  </>;
}
function ForumPosts({scope}: {scope:ActivityScope}) {
  const {user,loading:authLoading} = useAuth();
  const {data,loading,error} = useApi<ProfilePost[]>(authLoading ? null : "/forum/posts?scope="+scope+"&viewer="+(user?.id ?? "guest"));
  return <><ErrorMessage error={error}/>{authLoading || loading ? <Loading/> : !error && <ProfilePosts posts={data ?? []} forum title={scope === "mine" ? "Мои посты" : scope === "friends" ? "Посты друзей" : "Посты пользователей"}/>}</>;
}
function ForumContent() {
  const params = useSearchParams();
  const {user,loading} = useAuth();
  const [scope,setScope] = useState<ActivityScope>(activityScopes.find(item=>item.id === params.get("scope"))?.id ?? "all");
  const [tab,setTab] = useState<"posts" | "pacts">(params.has("pact") || params.has("topic") ? "pacts" : "posts");
  function changeScope(value:ActivityScope) {setScope(value);const query = new URLSearchParams(params.toString());if(value === "all") query.delete("scope");else query.set("scope",value);window.history.replaceState(null,"","/forum"+(query.size ? "?"+query.toString() : ""));}
  function select(value:"posts" | "pacts") {setTab(value);if(value === "posts" && (params.has("pact") || params.has("topic"))) window.history.replaceState(null,"","/forum"+(scope === "all" ? "" : "?scope="+scope));}
  return <><ActivityFilters current={scope} onChange={changeScope} signedIn={!!user} loading={loading}/><nav className="forum-main-tabs" aria-label="Разделы форума"><button aria-pressed={tab === "posts"} onClick={()=>select("posts")}><Icon name="image"/>Посты</button><button aria-pressed={tab === "pacts"} onClick={()=>select("pacts")}><Icon name="message"/>Обсуждения пактов</button></nav>{tab === "posts" ? <ForumPosts key={scope} scope={scope}/> : <PactForum scope={scope}/>}</>;
}
export default function ForumPage() {return <Shell><Suspense fallback={<Loading/>}><ForumContent/></Suspense></Shell>;}
