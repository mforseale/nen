import type { Audience } from "./community";

export type PostDraft = {
  version: 1; updatedAt: number; title: string; content: string; url: string; visibility: Audience;
  retainedIds: number[]; files: File[]; removeImage: boolean; pinNew: boolean; missingFiles?: boolean;
};
const DATABASE = "nen-post-drafts";
const STORE = "drafts";
const FILES = "attachments";
type StoredDraft = PostDraft & { attachmentSet?: string };
const attachmentSets = new WeakMap<File[], string>();
const queues = new Map<string, Promise<unknown>>();
function attachmentSet(files: File[]) {
  if (!files.length) return undefined;
  let id = attachmentSets.get(files);
  if (!id) { id = crypto.randomUUID(); attachmentSets.set(files, id); }
  return id;
}
function textBackup(draft: PostDraft) {
  return JSON.stringify({ ...draft, files: [], attachmentSet: attachmentSet(draft.files), missingFiles: draft.files.length > 0 });
}
/** Small synchronous checkpoint; never serializes file bytes on the typing path. */
export function checkpointPostDraft(key: string, draft: PostDraft) {
  const text = textBackup(draft);
  localStorage.setItem(DATABASE + key, text);
  localStorage.removeItem(DATABASE + key + ":cleared");
  return text;
}
export function postDraftKey(userId: number, postId?: number) { return `user:${userId}:post:${postId ?? "new"}`; }
function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") { reject(new Error("Хранилище черновиков недоступно.")); return; }
    const request = indexedDB.open(DATABASE, 2);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE);
      if (!request.result.objectStoreNames.contains(FILES)) request.result.createObjectStore(FILES);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
async function readDraft(key: string): Promise<StoredDraft | undefined> {
  const database = await open();
  return new Promise((resolve, reject) => {
    // One snapshot of both stores: another tab cannot mix new files with old text.
    const tx = database.transaction([STORE, FILES], "readonly");
    const metadata = tx.objectStore(STORE).get(key), attachments = tx.objectStore(FILES).get(key);
    tx.oncomplete = () => {
      database.close();
      const saved = metadata.result as StoredDraft | undefined, files = attachments.result as File[] | undefined;
      if (!saved?.attachmentSet) { resolve(saved); return; }
      if (files) attachmentSets.set(files, saved.attachmentSet);
      resolve({ ...saved, files: files ?? [], missingFiles: !files });
    };
    tx.onerror = tx.onabort = () => { database.close(); reject(tx.error || new Error("Не удалось открыть черновик.")); };
  });
}
async function writeDraft(key: string, draft: PostDraft | null) {
  const database = await open();
  return new Promise<void>((resolve, reject) => {
    const tx = database.transaction([STORE, FILES], "readwrite");
    const drafts = tx.objectStore(STORE), files = tx.objectStore(FILES);
    tx.oncomplete = () => { database.close(); resolve(); };
    tx.onerror = tx.onabort = () => { database.close(); reject(tx.error || new Error("Не удалось сохранить черновик.")); };
    if (!draft) { drafts.delete(key); files.delete(key); return; }
    const nextSet = attachmentSet(draft.files), previous = drafts.get(key);
    previous.onsuccess = () => {
      try {
        const saved = previous.result as StoredDraft | undefined;
        // File[] is stable while typing: only changed attachments write Blob data.
        if (nextSet !== saved?.attachmentSet || saved?.files.length) {
          if (draft.files.length) files.put(draft.files, key);
          else files.delete(key);
        }
        drafts.put({ ...draft, files: [], attachmentSet: nextSet } satisfies StoredDraft, key);
      } catch { tx.abort(); }
    };
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
  let fallback: StoredDraft | null = null;
  try {
    const raw = localStorage.getItem(DATABASE + key);
    if (raw) fallback = JSON.parse(raw) as StoredDraft;
  } catch {}
  const saved = await readDraft(key).catch(() => undefined);
  // Quota errors may block writes while reads still succeed with an older version.
  const chosen = fallback && (!saved || fallback.updatedAt >= saved.updatedAt) ? fallback : saved ?? null;
  if (!chosen?.attachmentSet || chosen.attachmentSet !== saved?.attachmentSet) return chosen;
  return { ...chosen, files: saved.files, missingFiles: saved.missingFiles };
}
export function savePostDraft(key: string, draft: PostDraft): Promise<void> {
  let checkpoint: string | null = null;
  try { checkpoint = checkpointPostDraft(key, draft); } catch {}
  return serial(key, async () => {
    try {
      await writeDraft(key, draft);
      // An older save must not clear text typed while that save was in flight.
      try { if (checkpoint !== null && localStorage.getItem(DATABASE + key) === checkpoint) localStorage.removeItem(DATABASE + key); } catch {}
    }
    catch {
      if (checkpoint === null) throw new Error("Браузер не смог сохранить черновик. Не закрывай редактор до публикации.");
      if (draft.files.length) throw new Error("Текст сохранён, но браузер не смог сохранить файлы. Не закрывай редактор до публикации.");
    }
  });
}
export function deletePostDraft(key: string): Promise<void> {
  return serial(key, async () => {
    try { localStorage.setItem(DATABASE + key + ":cleared", "1"); } catch {}
    await writeDraft(key, null).catch(() => {});
    try { localStorage.removeItem(DATABASE + key); } catch {}
  });
}
