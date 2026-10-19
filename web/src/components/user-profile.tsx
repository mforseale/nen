"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { api, checkinPayload, formatDate, isExpired, localDay, refreshData, useApi, type Pact, type Tier } from "@/lib/api";
import type { BatchCheckin, ProfileData } from "@/lib/community";
import type { DirectionName } from "@/lib/directions";
import { PactSeal } from "./pact-seal";
import { JointForm } from "./pact-detail";
import { PersonalPactForm, SettingsForm } from "./profile-editors";
import { Achievements, Avatar, FriendControls, ProfilePosts } from "./profile-sections";
import { PinnedFiles } from "./profile-files";
import { ProfileOverview } from "./profile-overview";
import { ProfilePactList } from "./profile-pact-list";
import { ProfileTabs, useProfileTab } from "./profile-tabs";
import { Action, Empty, ErrorMessage, Icon, Loading } from "./ui";

export function UserProfile({data}: {data:ProfileData}) {
  const {user,logout} = useAuth();
  const owner = user?.id === data.user.id;
  const router = useRouter();
  const params = useSearchParams();
  const targetPact = owner ? Number(params.get("pact")) || null : null;
  const {tab,change} = useProfileTab(owner);
  const pacts = useApi<Pact[]>(owner ? "/my/pacts" : null);
  const [joint,setJoint] = useState(false);
  const [personal,setPersonal] = useState(false);
  const [settings,setSettings] = useState(false);
  const [direction,setDirection] = useState<DirectionName|null>(null);
  const [defaults,setDefaults] = useState<{category:DirectionName;rarity:Tier}>({category:"Другое",rarity:"common"});
  const [batchMessage,setBatchMessage] = useState("");
  const records = pacts.data ?? [];
  const active = records.filter(pact=>pact.status === "active");
  const completed = records.filter(pact=>pact.status === "completed");
  const days = new Set(records.flatMap(pact=>pact.checkins)).size;
  const eligible = active.filter(pact=>!isExpired(pact) && !pact.checkins.includes(localDay()) && (!pact.duration_days || pact.checkins.length<pact.duration_days));
  return <div className="profile-page compact-profile" data-accent={data.accent}>
    <section className="profile-identity profile-identity-expanded"><Avatar person={data.user} large/><div className="profile-identity-copy"><p className="eyebrow">ПРОФИЛЬ</p><h1>{data.user.full_name}</h1><p className="muted">@{data.user.username} · В Nen с {formatDate(data.created_at)}</p>{data.bio && <details className="profile-bio-disclosure"><summary>О себе</summary><p className="profile-bio">{data.bio}</p></details>}{owner && <div className="profile-inline-stats"><span><b>{pacts.loading ? "—" : active.length}</b> активных</span><span><b>{pacts.loading ? "—" : completed.length}</b> завершено</span><span><b>{pacts.loading ? "—" : days}</b> дней с отметками</span></div>}</div>
      {owner ? <div className="profile-header-controls"><button className="button" onClick={()=>setSettings(true)}><Icon name="settings"/>Настройки</button><Action className="button-quiet" onClick={async()=>{await logout();router.push("/");}}><Icon name="logout"/>Выйти</Action></div> : <div className="public-profile-actions"><FriendControls username={data.user.username} relationship={data.friendship}/>{user ? <button className="button button-quiet" onClick={()=>setJoint(true)}>Предложить пакт <Icon name="link"/></button> : <Link className="button button-quiet" href="/login">Предложить пакт <Icon name="arrow"/></Link>}</div>}
    </section>
    <ProfileTabs current={tab} onChange={change} owner={owner}/>
    <div role="tabpanel" id="profile-panel-overview" aria-labelledby="profile-tab-overview" hidden={tab!=="overview"}>{tab === "overview" && <>{owner && <ErrorMessage error={pacts.error}/>}<ProfileOverview data={data} owner={owner} pacts={records} onNavigate={change} onDirection={owner ? category=>{setDirection(category ?? null);change("pacts");} : undefined}/></>}</div>
    {owner && <div role="tabpanel" id="profile-panel-pacts" aria-labelledby="profile-tab-pacts" hidden={tab!=="pacts"}>{tab === "pacts" && <>
      <div className="pacts-checkin-toolbar"><div><strong>Ежедневный прогресс</strong><p>Отмечай выполненные сегодня обязательства.</p></div><div className="module-actions"><button className="button" onClick={()=>setPersonal(true)}><Icon name="plus"/>Свой пакт</button><Action className="button-red" disabled={pacts.loading || !!pacts.error || !eligible.length} onClick={async()=>{const result=await api<BatchCheckin>("/my/pacts/checkin-all","POST",checkinPayload());setBatchMessage(`Отмечено: ${result.marked.length}. Уже отмечены: ${result.already_marked.length}.${result.expired.length ? ` Срок истёк: ${result.expired.length}.` : ""}`);refreshData();}}><Icon name="check"/>Отметить все{eligible.length>0 && ` (${eligible.length})`}</Action></div></div>
      {batchMessage && <p className="batch-result" role="status">{batchMessage}</p>}<ErrorMessage error={pacts.error}/>{pacts.loading ? <Loading/> : !pacts.error && <><PactSeal key={String(targetPact)+":"+active.some(pact=>pact.id === targetPact)} initialPactId={targetPact} initialCategory={direction} pacts={active} onCreate={(category,rarity)=>{setDefaults({category,rarity});setPersonal(true);}}/><ProfilePactList pacts={records}/></>}
      <div className="profile-pact-links"><Link className="button button-quiet" href="/">Направления пактов <Icon name="arrow"/></Link><button className="button button-quiet" onClick={()=>setJoint(true)}><Icon name="friends"/>Совместный пакт</button><Link className="text-link" href="/calendars"><Icon name="calendar"/>Календарь</Link><Link className="text-link" href="/notes"><Icon name="feather"/>Заметки</Link></div>
    </>}</div>}
    <div role="tabpanel" id="profile-panel-feed" aria-labelledby="profile-tab-feed" hidden={tab!=="feed"}>{tab === "feed" && <div className="profile-feed-layout"><ProfilePosts posts={data.posts} owner={owner}/><aside><PinnedFiles files={data.pins ?? []} owner={owner} compact/></aside></div>}</div>
    <div role="tabpanel" id="profile-panel-achievements" aria-labelledby="profile-tab-achievements" hidden={tab!=="achievements"}>{tab === "achievements" && <Achievements items={data.achievements}/>}</div>
    <div role="tabpanel" id="profile-panel-notes" aria-labelledby="profile-tab-notes" hidden={tab!=="notes"}>{tab === "notes" && <section className="public-notes-tab"><div className="section-heading"><h2>{owner ? "Мои заметки" : "Заметки, которыми делятся"}</h2>{owner && <Link className="button" href="/notes"><Icon name="feather"/>Управлять заметками</Link>}</div>{data.notes?.length ? <div className="notes-grid">{data.notes.map(note=><Link href={"/notes/"+note.id} key={note.id} className="note-card"><div className="note-card-meta"><time>{formatDate(note.created_at)}</time><Icon name={note.visibility === "public" ? "globe" : note.visibility === "private" ? "lock" : "user"}/></div><h2>{note.title}</h2><p>{note.content}</p><div className="note-card-bottom"><span>Читать запись</span><Icon name="arrow"/></div></Link>)}</div> : <Empty title="Нет доступных заметок"/>}</section>}</div>
    {owner && personal && <PersonalPactForm defaultCategory={defaults.category} defaultRarity={defaults.rarity} onClose={()=>setPersonal(false)}/>}
    {joint && user && <JointForm recipient={owner ? "" : data.user.username} onClose={()=>setJoint(false)}/>}
    {owner && settings && <SettingsForm profile={data} onClose={()=>setSettings(false)}/>}
  </div>;
}
