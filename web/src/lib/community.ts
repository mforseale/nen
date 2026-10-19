import type { Note, Person } from "./api";

export const pactCategories = ["Тело", "Социум", "Дисциплина", "Разум", "Созидание", "Другое"];
export const audiences = { private: "Только я", friends: "Друзья", public: "Все" } as const;
export type Audience = keyof typeof audiences;
export type PostKind = "post" | "image" | "music" | "film" | "book" | "link"; // Legacy records keep their stored kind.
export type Achievement = { id: string; title: string; description: string; count: number; target: number; earned: boolean; group: "path" | "tier" | "topic"; tier: string | null };
export type YearGoal = { id: number; year: number; title: string; description: string; target: number; current: number; unit: string; visibility: Audience };
export type ProfileFile = { id: number; post_id: number | null; name: string; kind: "image" | "audio" | "video" | "file"; media_type: string; size: number; pinned: boolean; visibility: Audience; url: string; download_url: string; created_at: string };
export type ProfilePost = { id: number; kind: PostKind; title: string; content: string; url: string; visibility: Audience; image_url: string | null; created_at: string; updated_at: string; attachments?: ProfileFile[]; author?: Person };
export type Friendship = { id: number; person: Person; status: "pending" | "accepted" | "declined"; incoming: boolean; created_at: string };
export type Relationship = { status: "none" | "self" | "incoming" | "outgoing" | "friends"; id: number | null };
export type ProfileData = { user: Person; created_at: string; bio: string; accent: "crimson" | "silver" | "gold"; friend_count: number; friendship: Relationship; friend_preview?: Person[]; pins?: ProfileFile[]; achievements: Achievement[]; goals: YearGoal[]; posts: ProfilePost[]; notes?: Note[] };
export type BatchCheckin = { marked: number[]; already_marked: number[]; expired: number[]; at_limit: number[] };

export function goalPercent(goal: Pick<YearGoal, "current" | "target">) {
  return goal.target > 0 ? Math.min(100, Math.max(0, Math.round(goal.current / goal.target * 100))) : 0;
}

/** Uploaded files become small raster images; external services never receive them. */
export async function prepareImage(file: File, avatar = false): Promise<string> {
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) throw new Error("Выбери PNG, JPEG или WebP.");
  if (file.size > 10 * 1024 * 1024) throw new Error("Исходный файл должен быть не больше 10 МиБ.");
  const bitmap = await createImageBitmap(file).catch(() => { throw new Error("Не удалось открыть картинку."); });
  try {
    const canvas = document.createElement("canvas");
    const max = avatar ? 512 : 1200;
    const scale = Math.min(1, max / Math.max(bitmap.width, bitmap.height));
    canvas.width = avatar ? Math.min(512, bitmap.width, bitmap.height) : Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = avatar ? canvas.width : Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Не удалось подготовить картинку.");
    context.fillStyle = "#111111"; context.fillRect(0, 0, canvas.width, canvas.height);
    if (avatar) {
      const side = Math.min(bitmap.width, bitmap.height);
      context.drawImage(bitmap, (bitmap.width - side) / 2, (bitmap.height - side) / 2, side, side, 0, 0, canvas.width, canvas.height);
    } else context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    for (const quality of [.9, .75, .6]) {
      const result = canvas.toDataURL("image/jpeg", quality);
      if (result.length < 1_390_000) return result;
    }
    throw new Error("Картинка слишком большая. Выбери файл поменьше.");
  } finally { bitmap.close(); }
}
