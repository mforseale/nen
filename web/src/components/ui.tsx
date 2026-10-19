"use client";

import { Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import SiteHeader from "./site-header";

export function Icon({ name, size = 24, className = "" }: { name: string; size?: number; className?: string }) {
  const paths: Record<string, ReactNode> = {
    search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4.5 4.5"/></>,
    arrow: <><path d="M4 12h16m-6-6 6 6-6 6"/></>,
    plus: <path d="M12 5v14M5 12h14"/>, close: <path d="m6 6 12 12M6 18 18 6"/>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/><path d="M12 2V1"/></>,
    user: <><circle cx="12" cy="8" r="3.5"/><path d="M5 21v-3a7 7 0 0 1 14 0v3"/></>,
    check: <path d="m5 12 4 4L19 6"/>, chevron: <path d="m9 5 7 7-7 7"/>,
    sun: <><circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/></>,
    moon: <path d="M20 14a8.5 8.5 0 0 1-10-10A8.5 8.5 0 1 0 20 14Z"/>,
    book: <><path d="M12 5v16M3 3c4 0 6 0 9 2 3-2 5-2 9-2v15c-4 0-6 0-9 3-3-3-5-3-9-3Z"/></>,
    compass: <><circle cx="12" cy="12" r="9"/><path d="m16 8-2.5 5.5L8 16l2.5-5.5Z"/></>,
    eye: <><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></>,
    feather: <><path d="M20 3c-9-3-15 3-13 12l5-1c8-2 9-6 8-11ZM4 21 17 6M7 14h5"/></>,
    flame: <path d="M13 2c2 7-5 7-3 12 2-1 4-4 4-6 7 6 7 13-2 14C2 22 3 13 7 9c-1 5 1 5 2 6-2-8 4-8 4-13Z"/>,
    mountain: <><path d="m2 20 8-15 5 8 3-4 5 11Z"/><path d="m7 11 3 2 3-2"/></>,
    star: <path d="m12 2 2.8 6.6L22 9l-5.5 4.7 1.8 7.3-6.3-4-6.3 4 1.8-7.3L2 9l7.2-.4Z"/>,
    sword: <><path d="m4 20 5-5m-3-3 6 6M9 15l10-10 2-2-1 5-8 10M3 21l2-2"/></>,
    infinity: <path d="M12 12c-8-13-17 6-6 6 5 0 7-12 12-12 10 0 5 18-6 6Z"/>,
    heart: <path d="M12 21S1 14 2 7c1-6 8-6 10-1 2-5 9-5 10 1 1 7-10 14-10 14Z"/>,
    link: <><path d="m9 15 6-6m-6-3 2-2a5 5 0 0 1 7 7l-2 2m-1 5-2 2a5 5 0 0 1-7-7l2-2"/></>,
    lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2"/></>,
    globe: <><circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 2v6m10-6v6M3 11h18"/></>,
    message: <path d="M21 15a3 3 0 0 1-3 3H9l-6 4V5a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3Z"/>,
    trash: <><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7"/></>,
    logout: <><path d="M10 3H4v18h6m3-5 5-4-5-4m-5 4h13"/></>,
    grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
    list: <><path d="M8 5h13M8 12h13M8 19h13"/><circle cx="3" cy="5" r=".7"/><circle cx="3" cy="12" r=".7"/><circle cx="3" cy="19" r=".7"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/></>,
    settings: <><path d="m10 3-1 3-3 1-3-1-1 4 2 2-1 3 3 3 3-1 2 2 4-1 1-3 3-1 1-4-2-2-1-3-4-1Z"/><circle cx="11" cy="11" r="3"/></>,
    seal: <><circle cx="12" cy="12" r="9"/><path d="m12 5 7 7-7 7-7-7ZM9 9l6 6m0-6-6 6"/></>,
    friends: <><circle cx="9" cy="7" r="3"/><path d="M2 21v-3a7 7 0 0 1 14 0v3M16 4a3 3 0 0 1 0 6m3 3a6 6 0 0 1 3 5v3"/></>,
    award: <><path d="m8 13-2 9 6-3 6 3-2-9"/><circle cx="12" cy="8" r="6"/><path d="m10 8 1.5 1.5L14 6"/></>,
    target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><path d="m12 12 8-8M17 3h4v4"/></>,
    image: <><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="m3 18 6-6 4 4 3-4 5 6"/></>,
    music: <><path d="M9 18V5l12-3v13M9 8l12-3"/><ellipse cx="6" cy="18" rx="3" ry="3"/><ellipse cx="18" cy="15" rx="3" ry="3"/></>,
    film: <><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4m-4 8h4m10-8h4m-4 8h4m-10-8 4 4-4 3Z"/></>,
    file: <path d="M14 2H5v20h14V7ZM14 2v5h5M8 12h8M8 16h6"/>,
    pin: <path d="m15 3 6 6-3 1-4 4-1 4-7-7 4-1 4-4ZM3 21l6-6"/>,
    upload: <path d="M12 16V3m-5 5 5-5 5 5M3 15v6h18v-6"/>,
    download: <path d="M12 3v13m-5-5 5 5 5-5M3 17v4h18v-4"/>,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">{paths[name] ?? paths.star}</svg>;
}

export function Shell({ children, home = false }: { children: ReactNode; home?: boolean }) {
  return <div className={`site-shell ${home ? "home-shell" : ""}`}>{home && <div className="home-background" aria-hidden="true"/>}<Suspense fallback={<header className="site-header"><Link href="/" className="brand">nen.</Link></header>}><SiteHeader/></Suspense><main className={`page-content ${home ? "home-content" : ""}`}>{children}</main><footer className="site-footer"><Link href="/" className="footer-logo">Nen<span>®</span></Link></footer></div>;
}

export function PageTitle({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return <div className="page-title"><div>{eyebrow && <p className="eyebrow"><span/> {eyebrow}</p>}<h1>{title}</h1></div>{children}</div>;
}

export function ErrorMessage({ error }: { error?: string | null }) { return error ? <p className="error-message" role="alert">{error}</p> : null; }
export function Empty({ title, children }: { title: string; children?: ReactNode }) { return <div className="empty-state"><span className="empty-ornament">✧</span><h3>{title}</h3>{children}</div>; }
export function Loading() { return <div className="loading" role="status"><span/>Загружаем…</div>; }

export function Modal({ title, children, onClose, className = "" }: { title: string; children: ReactNode; onClose: () => void; className?: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const backdropPress = useRef<{ x: number; y: number } | null>(null);
  useEffect(() => { const el = dialog.current; el?.showModal(); return () => {el?.close();}; }, []);
  function outside(element: HTMLDialogElement, x: number, y: number) {
    const rect = element.getBoundingClientRect();
    return x < rect.left || x > rect.right || y < rect.top || y > rect.bottom;
  }
  return <dialog ref={dialog} className={"nen-dialog "+className} onCancel={event => {
    event.stopPropagation();
    // File inputs emit a bubbling cancel when their native picker is dismissed.
    if (event.target !== event.currentTarget) return;
    event.preventDefault();onClose();
  }} onPointerDown={event => {
    backdropPress.current = event.button === 0 && event.target === event.currentTarget && outside(event.currentTarget,event.clientX,event.clientY) ? {x:event.clientX,y:event.clientY} : null;
  }} onPointerCancel={() => {backdropPress.current = null;}} onClick={event => {
    const start = backdropPress.current;backdropPress.current = null;
    if (start && event.target === event.currentTarget && outside(event.currentTarget,event.clientX,event.clientY) && Math.hypot(event.clientX-start.x,event.clientY-start.y) <= 6) onClose();
  }} aria-label={title}><div className="dialog-header"><p className="eyebrow">NEN / ОБЯЗАТЕЛЬСТВА</p><button type="button" className="icon-button" onClick={onClose} aria-label="Закрыть"><Icon name="close"/></button></div><h2>{title}</h2>{children}</dialog>;
}

export function Action({ children, onClick, className = "", disabled = false }: { children: ReactNode; onClick: () => Promise<unknown>; className?: string; disabled?: boolean }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);
  return <><button className={`button ${className}`} disabled={busy || disabled} onClick={async () => {setBusy(true);setError(null);try {await onClick();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}}>{busy ? "Сохраняем…" : children}</button><ErrorMessage error={error}/></>;
}
