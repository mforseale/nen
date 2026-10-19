import type { Audience } from "./community";

export type PostDraft = {
  version: 1; updatedAt: number; title: string; content: string; url: string; visibility: Audience;
  retainedIds: number[]; files: File[]; removeImage: boolean; pinNew: boolean; missingFiles?: boolean;
};
const DATABASE = "nen-post-drafts";
const STORE = "drafts";
const queues = new Map<string, Promise<unknown>>();
export function postDraftKey(userId: number, postId?: number) { return `user:${userId}:post:${postId ?? "new"}`; }
function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") { reject(new Error("Хранилище черновиков недоступно.")); return; }
    const request = indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
async function transaction<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const database = await open();
  return new Promise((resolve, reject) => {
    const tx = database.transaction(STORE, mode), request = action(tx.objectStore(STORE));
    tx.oncomplete = () => { database.close(); resolve(request.result); };
    tx.onerror = tx.onabort = () => { database.close(); reject(tx.error || request.error || new Error("Не удалось сохранить черновик.")); };
  });
}
function serial<T>(key: string, action: () => Promise<T>): Promise<T> {
  const next = (queues.get(key) ?? Promise.resolve()).catch(() => {}).then(action);
  queues.set(key, next);
  void next.finally(() => { if (queues.get(key) === next) queues.delete(key); }).catch(() => {});
  return next;
}
export async function loadPostDraft(key: string): Promise<PostDraft | null> {
  await queues.get(key)?.catch(() => {});
  // A successful publish stays cleared even if IndexedDB was momentarily locked.
  try { if (localStorage.getItem(DATABASE + key + ":cleared")) return null; } catch {}
  let fallback: PostDraft | null = null;
  try {
    const raw = localStorage.getItem(DATABASE + key);
    if (raw) fallback = JSON.parse(raw) as PostDraft;
  } catch {}
  const saved = await transaction<PostDraft | undefined>("readonly", store => store.get(key)).catch(() => undefined);
  // Quota errors may block writes while reads still succeed with an older version.
  return fallback && (!saved || fallback.updatedAt >= saved.updatedAt) ? fallback : saved ?? null;
}
export function savePostDraft(key: string, draft: PostDraft): Promise<void> {
  return serial(key, async () => {
    try {
      await transaction("readwrite", store => store.put(draft, key));
      try { localStorage.removeItem(DATABASE + key); localStorage.removeItem(DATABASE + key + ":cleared"); } catch {}
    }
    catch {
      localStorage.setItem(DATABASE + key, JSON.stringify({ ...draft, files: [], missingFiles: draft.files.length > 0 }));
      localStorage.removeItem(DATABASE + key + ":cleared");
      if (draft.files.length) throw new Error("Текст сохранён, но браузер не смог сохранить файлы. Не закрывай редактор до публикации.");
    }
  });
}
export function deletePostDraft(key: string): Promise<void> {
  return serial(key, async () => {
    try { localStorage.setItem(DATABASE + key + ":cleared", "1"); } catch {}
    await transaction("readwrite", store => store.delete(key)).catch(() => {});
    try { localStorage.removeItem(DATABASE + key); } catch {}
  });
}
