/** Small, deliberately HTML-free markup vocabulary used by posts and comments. */
export type InlinePart = { kind: "text" | "bold" | "italic" | "underline" | "strike" | "code" | "link"; text: string; href?: string };
export function safePostUrl(value: string): string | null {
  try {
    const url = new URL(value.trim());
    return ["https:", "http:"].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}
export function inlineParts(value: string): InlinePart[] {
  const pattern = /(\*\*([^*\n]+)\*\*|\+\+([^+\n]+)\+\+|~~([^~\n]+)~~|`([^`\n]+)`|\*([^*\n]+)\*|\[([^\]\n]+)\]\(([^\s)]+)\))/g;
  const parts: InlinePart[] = []; let cursor = 0;
  for (const match of value.matchAll(pattern)) {
    if (match.index! > cursor) parts.push({ kind: "text", text: value.slice(cursor, match.index) });
    if (match[2]) parts.push({ kind: "bold", text: match[2] });
    else if (match[3]) parts.push({ kind: "underline", text: match[3] });
    else if (match[4]) parts.push({ kind: "strike", text: match[4] });
    else if (match[5]) parts.push({ kind: "code", text: match[5] });
    else if (match[6]) parts.push({ kind: "italic", text: match[6] });
    else {
      const href = safePostUrl(match[8]);
      parts.push(href ? { kind: "link", text: match[7], href } : { kind: "text", text: match[0] });
    }
    cursor = match.index! + match[0].length;
  }
  if (cursor < value.length) parts.push({ kind: "text", text: value.slice(cursor) });
  return parts;
}
export function applyPostFormat(value: string, start: number, end: number, before: string, after = before, placeholder = "текст") {
  const selected = value.slice(start, end) || placeholder;
  return { value: value.slice(0, start) + before + selected + after + value.slice(end), start: start + before.length, end: start + before.length + selected.length };
}
