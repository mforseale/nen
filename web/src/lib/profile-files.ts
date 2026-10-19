import { API_URL } from "./api";

export const MAX_FILE_SIZE = 25 * 1024 * 1024;
export const MAX_POST_SIZE = 50 * 1024 * 1024;
export const MAX_FILES = 10;
export function fileSize(bytes: number) {
  if (bytes < 1024) return bytes + " Б";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " КиБ";
  return (bytes / (1024 * 1024)).toFixed(1) + " МиБ";
}
export function fileExtension(name: string) { return name.includes(".") ? name.split(".").pop()!.slice(0, 7).toUpperCase() : "ФАЙЛ"; }
export function fileIcon(kind: string) { return kind === "image" ? "image" : kind === "audio" ? "music" : kind === "video" ? "film" : "file"; }
export async function multipart<T>(path: string, method: string, body: FormData): Promise<T> {
  const response = await fetch(API_URL + path, { method, body, credentials: "include" });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === "string" ? data.detail : "Не удалось загрузить файлы. Проверь размер и параметры публикации.");
  }
  return response.json();
}
