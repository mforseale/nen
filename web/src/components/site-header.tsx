"use client";

import Link from "next/link";
/* eslint-disable @next/next/no-img-element -- User-uploaded avatars are already resized and served directly by the API. */
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useAuth } from "@/lib/auth";
import { profileHref } from "@/lib/profile-navigation";
import { api, useApi, type PactRequest, type Person } from "@/lib/api";
import type { Friendship } from "@/lib/community";
import { Icon } from "./ui";

type Result = { id: string | number; title: string; subtitle: string; href: string };
const categories = [
  { id: "pacts", label: "Пакты", icon: "sword", placeholder: "Найти свой пакт…" },
  { id: "users", label: "Пользователи", icon: "user", placeholder: "Имя или логин…" },
  { id: "notes", label: "Заметки", icon: "feather", placeholder: "Название или текст заметки…" },
] as const;
type SearchKind = typeof categories[number]["id"];

export default function SiteHeader() {
  const pathname = usePathname();
  const { user } = useAuth();
  const { data: requests, reload } = useApi<PactRequest[]>(user ? "/requests" : null);
  const { data: friends, reload: reloadFriends } = useApi<Friendship[]>(user ? "/friends" : null);
  const { data: profile } = useApi<Person>(user ? "/my/profile/identity" : null);
  useEffect(() => {
    if (!user) return;
    const refresh = () => { reload(); reloadFriends(); };
    const timer = setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    return () => { clearInterval(timer); window.removeEventListener("focus", refresh); };
  }, [user, reload, reloadFriends]);
  const pactPending = requests?.filter(r => r.incoming && r.status === "pending").length ?? 0;
  const friendPending = friends?.filter(r => r.incoming && r.status === "pending").length ?? 0;
  const pending = pactPending + friendPending;
  const [kind, setKind] = useState<SearchKind | null>(null);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<{ key: string; results: Result[]; error: string }>({ key: "", results: [], error: "" });
  const [open, setOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const selectedCategory = categories.find(category => category.id === kind);
  const searchKey = kind && query.trim() ? kind + ":" + query.trim() : "";
  const current = search.key === searchKey ? search : null;

  useEffect(() => {
    const outside = (event: PointerEvent) => {
      if (!searchRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, []);

  useEffect(() => {
    if (!searchKey || !kind) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api<Result[]>("/search?kind=" + kind + "&q=" + encodeURIComponent(query.trim()), "GET", undefined, controller.signal)
        .then(results => { if (!controller.signal.aborted) setSearch({ key: searchKey, results, error: "" }); })
        .catch(error => {
          if (!controller.signal.aborted) setSearch({ key: searchKey, results: [], error: error instanceof TypeError ? "Сервер поиска недоступен." : error.message });
        });
    }, 220);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [kind, query, searchKey]);

  function selectCategory(value: SearchKind) {
    setKind(value);
    setOpen(true);
    inputRef.current?.focus();
  }

  function searchKeyboard(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      inputRef.current?.focus();
      setOpen(false);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      const options = Array.from(searchRef.current?.querySelectorAll<HTMLElement>("[data-search-option]") ?? []);
      if (!options.length) return;
      const position = options.indexOf(event.target as HTMLElement);
      const next = event.key === "ArrowDown" ? position + 1 : position < 0 ? options.length - 1 : position - 1;
      options[(next + options.length) % options.length]?.focus();
    }
    if (event.key === "Enter" && event.target === inputRef.current) {
      event.preventDefault();
      if (!open) setOpen(true);
      if (!kind) searchRef.current?.querySelector<HTMLElement>("[data-search-option]")?.focus();
      else searchRef.current?.querySelector<HTMLElement>(".nav-search-result")?.click();
    }
  }

  return (
    <header className="site-header">
      <Link className="brand" href="/" aria-label="Nen — главная">
        <span className="brand-mark" lang="ja" aria-hidden="true">念</span><span>nen<span className="brand-dot">.</span></span>
      </Link>
      <nav className="primary-nav" aria-label="Основная навигация">
        {[
          { href: "/", label: "Пакты", icon: "seal" },
          { href: "/forum", label: "Форум", icon: "message" },
          { href: "/notes", label: "Заметки", icon: "feather" },
          { href: "/calendars", label: "Календарь", icon: "calendar" },
          { href: "/friends", label: "Друзья", icon: "friends" },
        ].map(({ href, label, icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return <Link key={href} href={href} className={active ? "active" : ""} aria-current={active ? "page" : undefined}><Icon name={icon} size={18}/><span>{label}</span></Link>;
        })}
      </nav>
      <div className="nav-search" ref={searchRef} onKeyDown={searchKeyboard} onBlur={event => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}>
        <div className="nav-search-field">
          <Icon name="search" size={19}/>
          {selectedCategory && <button className="nav-search-kind" aria-label="Выбрать категорию поиска" aria-expanded={open} onClick={() => {
            setOpen(value => !value);
            if (!open) inputRef.current?.focus();
          }}>{selectedCategory.label}</button>}
          <input
            ref={inputRef}
            type="search"
            role="combobox"
            aria-label="Поиск"
            aria-expanded={open}
            aria-controls="nav-search-popup"
            aria-haspopup="dialog"
            autoComplete="off"
            placeholder={selectedCategory?.placeholder ?? "Поиск…"}
            value={query}
            onFocus={() => setOpen(true)}
            onChange={event => { setQuery(event.target.value); setOpen(true); }}
          />
        </div>
        {open && <div className="nav-search-popup" id="nav-search-popup" role="dialog" aria-label="Категории и результаты поиска">
          <p className="nav-search-caption">Искать среди</p>
          <div className="nav-search-categories">
            {categories.map(category => <button
              key={category.id}
              data-search-option
              className={"nav-search-category " + (kind === category.id ? "selected" : "")}
              aria-pressed={kind === category.id}
              onClick={() => selectCategory(category.id)}
            ><Icon name={category.icon} size={18}/><span>{category.label}</span>{kind === category.id && <Icon name="check" size={16}/>}</button>)}
          </div>
          {searchKey && <div className="nav-search-matches" aria-busy={!current}>
            <p className="nav-search-caption">Результаты</p>
            {!current ? <p className="nav-search-status" role="status">Ищем…</p> :
              current.error ? <p className="nav-search-status" role="alert">{current.error}</p> :
              current.results.length ? current.results.map(item => <Link
                key={item.id}
                href={item.href}
                className="nav-search-result"
                data-search-option
                onClick={() => { setOpen(false); setQuery(""); }}
              ><span>{item.title}<small>{item.subtitle}</small></span><Icon name="arrow" size={17}/></Link>) :
              <p className="nav-search-status" role="status">Ничего не найдено</p>}
          </div>}
        </div>}
      </div>
      <div className="header-actions">
        <Link href={user ? friendPending && !pactPending ? "/friends" : "/requests" : "/login"} className={"notification-button icon-button " + (pathname === "/requests" ? "active" : "")} aria-label={pending ? "Входящие приглашения: " + pending : "Запросы и приглашения"}>
          <Icon name="bell"/>{pending > 0 && <span className="notification-dot">{pending}</span>}
        </Link>
        <span className="header-divider"/>
        <Link className="profile-button" href={user ? profileHref(user.username) : "/login"} aria-label={user ? "Мой профиль" : "Войти"}>
          {profile?.avatar_url ? <img src={profile.avatar_url} alt=""/> : user ? <span>{(user.full_name || user.username).slice(0, 1).toUpperCase()}</span> : <Icon name="user" size={18}/>}
        </Link>
      </div>
    </header>
  );
}

