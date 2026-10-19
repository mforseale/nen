"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { profileHref } from "@/lib/profile-navigation";
import { myPactsPath, tiers, useApi, type Pact, type Tier } from "@/lib/api";
import { pactDays } from "@/lib/pact-progress";
import { directions, directionOf, tierOrder, type DirectionName } from "@/lib/directions";
import { ErrorMessage, Icon, Loading, Shell } from "@/components/ui";
import { JointForm } from "@/components/pact-detail";
import { PersonalPactForm } from "@/components/profile-editors";
import { HomeDirections } from "@/components/home-directions";

function HomeContent() {
  const {user, loading:authLoading} = useAuth();
  const {data:mine,loading,error} = useApi<Pact[]>(user ? myPactsPath() : null);
  const params = useSearchParams();
  const [category,setCategory] = useState<DirectionName | null>(directions.find(item => item.name === params.get("category"))?.name ?? null);
  const [tier,setTier] = useState<Tier | "all">(tierOrder.find(item => item === params.get("tier")) ?? "all");
  const [personal,setPersonal] = useState(false);
  const [joint,setJoint] = useState(false);
  const [query,setQuery] = useState("");
  const active = (mine ?? []).filter(pact => pact.status === "active");
  const inDirection = active.filter(pact => !category || directionOf(pact) === category);
  const visible = inDirection.filter(pact => (tier === "all" || pact.rarity === tier) && (pact.title + " " + pact.description).toLocaleLowerCase("ru").includes(query.trim().toLocaleLowerCase("ru")));
  const direction = directions.find(item => item.name === category);
  return <Shell home>
    <section className="home-pact-stage" aria-labelledby="home-title">
      <div className="home-stage-heading"><div><p className="eyebrow">ШЕСТЬ НАПРАВЛЕНИЙ</p><h1 id="home-title">Мои пакты</h1></div><Link href={user ? profileHref(user.username,"","pacts") : "/login"} className="text-link"><Icon name="seal"/>Мой прогресс <Icon name="arrow"/></Link></div>
      <div className="home-stage-composition">
        <div className="home-direction-scene">
          <div className="home-chain-art" aria-hidden="true"/>
          <HomeDirections pacts={active} selected={category} onSelect={setCategory} loading={authLoading || loading}/>
        </div>
        <div className="home-direction-context" style={direction ? {borderColor:direction.color} : undefined}>
          <div className="home-context-title">{direction && <span style={{color:direction.color}} aria-hidden="true">{direction.glyph}</span>}<h2>{category ?? "Собственные условия"}</h2></div>
          <p>{direction?.description ?? "Создай пакт: определи условия, выбери направление и срок."}</p>
          <p className="home-capacity-note">Выбирай столько пактов, сколько нужно тебе.</p>
          {user ? <button className="button full-width" onClick={() => setPersonal(true)}><Icon name="plus"/>Создать свой пакт</button> : <Link href="/login" className="button full-width"><Icon name="plus"/>Создать свой пакт</Link>}
          {user ? <button className="text-link home-joint-action" onClick={() => setJoint(true)}><Icon name="link"/>Предложить совместный</button> : <Link href="/login" className="text-link home-joint-action"><Icon name="link"/>Предложить совместный</Link>}
        </div>
      </div>
    </section>
    <section className="home-own-pacts" id="home-own-pacts" aria-labelledby="home-pacts-title">
      <div className="home-pacts-heading"><h2 id="home-pacts-title">{category ?? "Все направления"}<span>{authLoading || loading ? "…" : inDirection.length}</span></h2>{category && <button className="text-link" onClick={() => setCategory(null)}>Все направления <Icon name="close" size={20}/></button>}</div>
      {authLoading ? <Loading/> : !user ? <div className="home-pacts-empty"><Icon name="lock" size={32}/><div><h3>Твои пакты будут здесь</h3><p>Войди, чтобы создавать пакты и отслеживать прогресс.</p></div><Link href="/login" className="button">Войти <Icon name="arrow"/></Link></div> : <>
        <div className="home-pacts-toolbar"><div className="home-tier-filters" role="group" aria-label="Тир пакта"><button aria-pressed={tier === "all"} onClick={() => setTier("all")}>Все тиры</button>{tierOrder.map(item => <button key={item} data-tier={item} aria-pressed={tier === item} onClick={() => setTier(item)}><span className={"tier-dot tier-"+item}/>{tiers[item].label}<small>{tiers[item].duration}</small></button>)}</div><label className="home-pact-search"><Icon name="search"/><input aria-label="Поиск среди своих пактов" placeholder="Найти свой пакт" value={query} onChange={event => setQuery(event.target.value)}/></label></div>
        <ErrorMessage error={error}/>{loading ? <Loading/> : !error && (visible.length ? <div className="home-pact-list">{visible.map(pact => <Link key={pact.id} href={profileHref(user?.username,`pact=${pact.id}`,"pacts")} className="home-pact-row" data-pact-id={pact.id} data-tier={pact.rarity}><span className={"tier tier-"+pact.rarity}>{tiers[pact.rarity].label}</span><div><h3>{pact.title}</h3><p>{directionOf(pact)}{pact.is_joint ? " · совместный" : ""} · {pactDays(pact)}{pact.duration_days ? ` / ${pact.duration_days} дней` : " дней"} · стрик {pact.streak_days ?? 0}</p></div><strong>{pact.progress === null ? "∞" : `${pact.progress}%`}</strong><Icon name="arrow"/></Link>)}</div> : <div className="home-pacts-empty"><Icon name="feather" size={32}/><div><h3>{query.trim() ? "Пакты не найдены" : "Здесь пока нет пактов"}</h3><p>{query.trim() ? "Попробуй другое название или сбрось фильтры." : "Напиши собственные условия и выбери срок."}</p></div><button className="button" onClick={() => setPersonal(true)}><Icon name="plus"/>Создать пакт</button></div>)}
      </>}
    </section>
    {personal && <PersonalPactForm defaultCategory={category ?? "Другое"} defaultRarity={tier === "all" ? "common" : tier} onClose={() => setPersonal(false)}/>}
    {joint && <JointForm onClose={() => setJoint(false)}/>}
  </Shell>;
}
export default function Home() {return <Suspense fallback={<Shell home><Loading/></Shell>}><HomeContent/></Suspense>;}
