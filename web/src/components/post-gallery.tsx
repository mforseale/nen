"use client";
/* eslint-disable @next/next/no-img-element -- Private originals require authenticated direct URLs. */

import {useCallback, useState, type CSSProperties} from "react";
import {galleryLayout} from "@/lib/post-gallery";
import {Icon} from "./ui";

export function PostGallery({images, compact, onOpen}: {images: {url: string; name: string}[]; compact: boolean; onOpen: (index: number) => void}) {
  const [ratios, setRatios] = useState<Record<string, number>>({});
  const measure = useCallback((url: string, image: HTMLImageElement | null) => {
    if (!image?.naturalWidth || !image.naturalHeight) return;
    const ratio = image.naturalWidth / image.naturalHeight;
    setRatios(previous => previous[url] === ratio ? previous : {...previous, [url]: ratio});
  }, []);
  const layout = galleryLayout(images.map(image => ratios[image.url] ?? 4 / 3));
  return <div className={"post-gallery post-mosaic" + (images.length === 1 ? " single" : "")} data-image-count={images.length} style={{"--gallery-aspect": layout.aspect, "--gallery-gap-adjustment": `${layout.gapAdjustment}px`} as CSSProperties}>
    {layout.rows.map((row, rowIndex) => <div className="post-gallery-row" key={rowIndex}>{row.indices.map((index, position) => {
      const image = images[index];
      return <div className="post-gallery-item" key={image.url} style={{flexGrow: row.ratios[position]}}><button type="button" onClick={() => onOpen(index)} aria-label={"Увеличить изображение " + (index + 1)}><img ref={element => {measure(image.url, element);}} onLoad={event => measure(image.url, event.currentTarget)} src={image.url} alt={"Изображение " + (index + 1)} loading={compact ? "lazy" : "eager"} style={{aspectRatio: row.ratios[position]}}/>{compact && <span className="post-image-hover"><Icon name="eye" size={25}/>Увеличить</span>}</button></div>;
    })}</div>)}
  </div>;
}
