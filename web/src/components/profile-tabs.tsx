"use client";
import { useSyncExternalStore } from "react";
import { Icon } from "./ui";

export const profileTabs=[{id:"overview",label:"Обзор",icon:"grid"},{id:"pacts",label:"Пакты",icon:"seal"},{id:"feed",label:"Лента",icon:"message"},{id:"achievements",label:"Достижения",icon:"award"},{id:"notes",label:"Заметки",icon:"feather"}] as const;
export type ProfileTab=typeof profileTabs[number]["id"];
function subscribe(listener:()=>void) {window.addEventListener("hashchange",listener);window.addEventListener("popstate",listener);return()=>{window.removeEventListener("hashchange",listener);window.removeEventListener("popstate",listener);};}
function snapshot():ProfileTab {return profileTabs.find(tab=>tab.id===window.location.hash.slice(1))?.id ?? "overview";}
export function profileTabsFor(owner:boolean) {return profileTabs.filter(tab=>owner || tab.id !== "pacts");}
export function useProfileTab(owner=false) {
  const tab=useSyncExternalStore(subscribe,snapshot,()=>"overview" as ProfileTab);
  return {tab:!owner && tab === "pacts" ? "overview" as ProfileTab : tab,change:(value:ProfileTab)=>{window.location.hash=value;}};
}
export function ProfileTabs({current,onChange,owner=false}:{current:ProfileTab;onChange:(tab:ProfileTab)=>void;owner?:boolean}) {
  const tabs=profileTabsFor(owner);
  return <nav className="profile-main-tabs" role="tablist" aria-label="Разделы профиля">{tabs.map((tab,index)=><button key={tab.id} id={"profile-tab-"+tab.id} role="tab" aria-selected={current === tab.id} aria-controls={"profile-panel-"+tab.id} tabIndex={current === tab.id ? 0 : -1} className={current === tab.id ? "active" : ""} onClick={()=>onChange(tab.id)} onKeyDown={event=>{let next=index;if(event.key === "ArrowRight")next=(index+1)%tabs.length;else if(event.key === "ArrowLeft")next=(index+tabs.length-1)%tabs.length;else if(event.key === "Home")next=0;else if(event.key === "End")next=tabs.length-1;else return;event.preventDefault();onChange(tabs[next].id);document.getElementById("profile-tab-"+tabs[next].id)?.focus();}}><Icon name={tab.icon}/><span>{tab.label}</span></button>)}</nav>;
}
