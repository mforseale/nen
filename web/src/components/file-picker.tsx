"use client";

import { useEffect, useId, useImperativeHandle, useRef, useState, type ComponentProps, type Ref } from "react";
import { Icon } from "./ui";

type Props = Omit<ComponentProps<"input">, "type"> & { inputRef?: Ref<HTMLInputElement>; selectionCount?: number };
export function FilePicker({ inputRef, selectionCount, onChange, multiple, id, ...props }: Props) {
  const generatedId = useId(), input = useRef<HTMLInputElement>(null);
  const [count, setCount] = useState(0);
  useImperativeHandle(inputRef, () => input.current!);
  useEffect(() => {
    const form = input.current?.form;
    const reset = () => setCount(0);
    form?.addEventListener("reset", reset);
    return () => form?.removeEventListener("reset", reset);
  }, []);
  useEffect(() => { if (selectionCount === 0 && input.current) input.current.value = ""; }, [selectionCount]);
  const selected = selectionCount ?? count;
  return <span className="file-picker">
    <input {...props} type="file" multiple={multiple} id={id ?? generatedId} className="file-picker-native" tabIndex={-1} aria-hidden="true" ref={input} onChange={event => { const next = event.currentTarget.files?.length ?? 0; onChange?.(event); setCount(next); }}/>
    <button type="button" className="button button-quiet file-picker-button" disabled={props.disabled} onClick={() => input.current?.click()}><Icon name="upload" size={20}/>{multiple ? "Выбрать файлы" : "Выбрать файл"}</button>
    <span className="file-picker-status" aria-live="polite">{selected ? multiple ? `Выбрано файлов: ${selected}` : "Файл выбран" : "Файл не выбран"}</span>
  </span>;
}
