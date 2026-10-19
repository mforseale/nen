"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useAuth } from "@/lib/auth";
import { profileHref } from "@/lib/profile-navigation";
import { ErrorMessage, Icon, Shell } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter(); const {login,register,user,loading} = useAuth();
  const [mode,setMode] = useState<"login" | "register">("login");const [error,setError] = useState<string | null>(null);const [busy,setBusy] = useState(false);
  useEffect(() => {if(!loading && user) router.replace(profileHref(user.username));}, [loading,user,router]);
  async function submit(e: FormEvent<HTMLFormElement>) {e.preventDefault();const form = new FormData(e.currentTarget);setBusy(true);setError(null);try{const password=String(form.get("password"));if(mode==="login") await login({login:String(form.get("login")),password});else await register({username:String(form.get("username")),full_name:String(form.get("full_name")),email:String(form.get("email")),password});}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
  return <Shell><section className="auth-layout"><div className="auth-form-panel"><h1>{mode==="login" ? "Вход в Nen" : "Регистрация"}</h1><form className="form-stack" onSubmit={submit}>{mode==="register" ? <><label>Имя<input name="full_name" autoComplete="name" placeholder="Как тебя зовут?" required minLength={2} maxLength={120}/></label><label>Логин<input name="username" autoComplete="username" placeholder="Твоё имя в Nen" pattern="[A-Za-z0-9_]{3,50}" required minLength={3} maxLength={50}/><small>Латинские буквы, цифры и подчёркивание</small></label><label>Почта<input name="email" type="email" autoComplete="email" placeholder="you@example.com" required maxLength={255}/></label></> : <label>Логин или почта<input name="login" autoComplete="username" placeholder="Твоё имя в Nen" required/></label>}<label>Пароль<input name="password" type="password" autoComplete={mode==="login" ? "current-password" : "new-password"} placeholder={mode==="login" ? "Твой пароль" : "Не менее 8 символов"} minLength={mode==="register" ? 8 : undefined} maxLength={128} required/></label><ErrorMessage error={error}/><button className="button button-light full-width" disabled={busy}>{busy ? "Подожди…" : mode==="login" ? "Войти в Nen" : "Создать профиль"}<Icon name="arrow" size={17}/></button></form><button className="auth-toggle" onClick={() => {setMode(mode==="login" ? "register" : "login");setError(null);}}>{mode==="login" ? "Нет аккаунта? Зарегистрироваться" : "Уже есть аккаунт? Войти"}</button><Link href="/" className="auth-back">← К пактам</Link></div></section></Shell>;
}
