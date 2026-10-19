export type GalleryRow = { indices: number[]; ratios: number[] };
const fallbackRatio = 4 / 3;

/** Each row shares a height; its widths follow the original image proportions. */
export function galleryLayout(values: number[], gap = 2): { rows: GalleryRow[]; aspect: number; gapAdjustment: number } {
  const ratios = values.map(value => Number.isFinite(value) && value > 0 ? value : fallbackRatio);
  const count = ratios.length;
  if (!count) return {rows: [], aspect: 1, gapAdjustment: 0};
  // A landscape lead followed by two smaller pictures matches the reference.
  const rowCount = Math.ceil(count / 3);
  const groups = count === 3 ? (ratios[0] >= 1.1 ? [1, 2] : [3]) :
    count <= 2 ? [count] : count === 4 ? [2, 2] : count === 5 ? [2, 3] :
    Array.from({length: rowCount}, (_, index) => Math.floor(count / rowCount) + Number(index >= rowCount - count % rowCount));
  let cursor = 0, inverseAspect = 0, gapAdjustment = -(groups.length - 1) * gap;
  const rows = groups.map(size => {
    const indices = Array.from({length: size}, () => cursor++);
    const rowRatios = indices.map(index => ratios[index]);
    const sum = rowRatios.reduce((total, value) => total + value, 0);
    inverseAspect += 1 / sum;
    gapAdjustment += (size - 1) * gap / sum;
    return {indices, ratios: rowRatios};
  });
  return {rows, aspect: 1 / inverseAspect, gapAdjustment};
}
