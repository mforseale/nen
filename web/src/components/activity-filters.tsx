"use client";
import Link from "next/link";
import { Icon } from "./ui";

export const activityScopes = [
  {id:"all",label:"Вся активность",icon:"globe"},
  {id:"friends",label:"Друзья",icon:"friends"},
  {id:"mine",label:"Моя",icon:"user"},
] as const;
export type ActivityScope = typeof activityScopes[number]["id"];

export function ActivityFilters({current,onChange,signedIn,loading=false}: {current:ActivityScope;onChange:(value:ActivityScope)=>void;signedIn:boolean;loading?:boolean}) {
  return <div className="forum-activity-navigation"><div className="activity-scope-filters" role="group" aria-label="Чья активность">{activityScopes.map(item=><button key={item.id} aria-pressed={current === item.id} disabled={loading || item.id !== "all" && !signedIn} onClick={()=>onChange(item.id)}><Icon name={item.icon}/><span>{item.label}</span></button>)}</div>{!signedIn && !loading && <p className="activity-sign-in"><Link href="/login">Войти</Link>, чтобы смотреть активность друзей и свою.</p>}</div>;
}
