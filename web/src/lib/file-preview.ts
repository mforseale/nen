/** Only the editor thumbnail is resized; the original File is kept for upload. */
export async function filePreview(file: File): Promise<Blob | null> {
  if (!/^image\/(png|jpeg|webp|gif)$/.test(file.type) || typeof createImageBitmap === "undefined") return null;
  let bitmap: ImageBitmap | undefined;
  try {
    bitmap = await createImageBitmap(file, { resizeWidth: 192, resizeQuality: "low" });
    const scale = Math.min(1, 192 / Math.max(bitmap.width, bitmap.height));
    const width = Math.max(1, Math.round(bitmap.width * scale)), height = Math.max(1, Math.round(bitmap.height * scale));
    if (typeof OffscreenCanvas !== "undefined") {
      const canvas = new OffscreenCanvas(width, height), context = canvas.getContext("2d");
      if (!context) return null;
      context.drawImage(bitmap, 0, 0, width, height);
      return await canvas.convertToBlob({ type: "image/webp", quality: .75 });
    }
    const canvas = document.createElement("canvas");
    canvas.width = width; canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) return null;
    context.drawImage(bitmap, 0, 0, width, height);
    return await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, "image/webp", .75));
  } catch { return null; }
  finally { bitmap?.close(); }
}
