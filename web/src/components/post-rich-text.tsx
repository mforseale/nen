"use client";

import { useId, useRef, useState } from "react";
import { applyPostFormat, inlineParts } from "@/lib/post-rich-text";
import { Icon } from "./ui";

function Inline({ text }: { text: string }) {
  return inlineParts(text).map((part, index) => {
    if (part.kind === "bold") return <strong key={index}>{part.text}</strong>;
    if (part.kind === "italic") return <em key={index}>{part.text}</em>;
    if (part.kind === "underline") return <u key={index}>{part.text}</u>;
    if (part.kind === "strike") return <s key={index}>{part.text}</s>;
    if (part.kind === "code") return <code key={index}>{part.text}</code>;
    if (part.kind === "link") return <a key={index} href={part.href} target="_blank" rel="noopener noreferrer">{part.text}</a>;
    return part.text;
  });
}
export function PostRichText({ content, className = "" }: { content: string; className?: string }) {
  return <div className={"post-rich-text " + className}>{content.split("\n").map((line, index) => line.startsWith("> ") ? <blockquote key={index}><Inline text={line.slice(2)}/></blockquote> : line.startsWith("- ") ? <div className="rich-list-line" key={index}><span aria-hidden="true">•</span><span><Inline text={line.slice(2)}/></span></div> : <div className="rich-line" key={index}>{line ? <Inline text={line}/> : <br/>}</div>)}</div>;
}
export function PostTextEditor({ value, onChange, disabled = false, onAttach, maxLength = 10000, label = "Текст", placeholder = "Поделись мыслями, впечатлениями или результатом" }: { value: string; onChange: (value: string) => void; disabled?: boolean; onAttach?: () => void; maxLength?: number; label?: string; placeholder?: string }) {
  const input = useRef<HTMLTextAreaElement>(null), id = useId();
  const [preview, setPreview] = useState(false), [link, setLink] = useState(false), [url, setUrl] = useState("");
  const selection = useRef({ start: 0, end: 0 });
  function format(before: string, after?: string, placeholder?: string) {
    const el = input.current;
    const start = el?.selectionStart ?? selection.current.start, end = el?.selectionEnd ?? selection.current.end;
    const next = applyPostFormat(value, start, end, before, after, placeholder);
    if (next.value.length > maxLength) return;
    onChange(next.value); setPreview(false);
    requestAnimationFrame(() => { input.current?.focus(); input.current?.setSelectionRange(next.start, next.end); });
  }
  const tools = [
    { label: "Жирный", text: <b>B</b>, before: "**" }, { label: "Курсив", text: <i>I</i>, before: "*" },
    { label: "Подчёркнутый", text: <u>U</u>, before: "++" }, { label: "Зачёркнутый", text: <s>S</s>, before: "~~" },
    { label: "Цитата", text: <span>❞</span>, before: "> ", after: "" }, { label: "Список", text: <Icon name="list" size={22}/>, before: "- ", after: "" },
    { label: "Код", text: <span className="code-tool">&lt;/&gt;</span>, before: "`" },
  ];
  return <div className="post-text-editor"><label htmlFor={id}>{label}</label><div className="post-editor-toolbar" role="toolbar" aria-label="Оформление текста">{tools.map(tool => <button key={tool.label} type="button" title={tool.label} aria-label={tool.label} disabled={disabled || preview} onMouseDown={event=>event.preventDefault()} onClick={()=>format(tool.before, tool.after)}>{tool.text}</button>)}<button type="button" title="Добавить ссылку" aria-label="Добавить ссылку" disabled={disabled || preview} onMouseDown={event=>event.preventDefault()} onClick={()=>{selection.current={start:input.current?.selectionStart ?? 0,end:input.current?.selectionEnd ?? 0};setLink(!link);}}><Icon name="link" size={22}/></button>{onAttach && <button type="button" title="Прикрепить изображения и файлы" aria-label="Прикрепить изображения и файлы" disabled={disabled} onClick={onAttach}><Icon name="image" size={22}/></button>}<button type="button" className="editor-preview-toggle" aria-pressed={preview} disabled={disabled} onClick={()=>setPreview(!preview)}><Icon name={preview ? "feather" : "eye"} size={21}/>{preview ? "Редактор" : "Просмотр"}</button></div>
    {link && <div className="editor-link-input"><input aria-label="Адрес ссылки" type="url" placeholder="https://…" value={url} onChange={event=>setUrl(event.target.value)}/><button type="button" className="button button-quiet" disabled={!/^https?:\/\//i.test(url)} onClick={()=>{const next=applyPostFormat(value,selection.current.start,selection.current.end,"[",`](${url})`,"ссылка");if(next.value.length<=maxLength)onChange(next.value);setLink(false);setUrl("");}}>Вставить</button></div>}
    {preview ? <PostRichText content={value || "Здесь появится текст поста."} className="editor-rich-preview"/> : <textarea id={id} name="content" ref={input} value={value} onChange={event=>onChange(event.target.value)} maxLength={maxLength} disabled={disabled} placeholder={placeholder} onKeyDown={event=>{if((event.ctrlKey || event.metaKey) && ["b","i","u"].includes(event.key.toLowerCase())){event.preventDefault();format(event.key.toLowerCase()==="b" ? "**" : event.key.toLowerCase()==="i" ? "*" : "++");}}}/>}<small className="editor-character-count">{value.length.toLocaleString("ru-RU")} / {maxLength.toLocaleString("ru-RU")}</small></div>;
}
