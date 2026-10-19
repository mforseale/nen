"use client";

import type { CSSProperties } from "react";
import { directions, directionOf, directionPoint, type DirectionName } from "@/lib/directions";
import type { Pact } from "@/lib/api";

export function HomeDirections({pacts, selected, onSelect, loading = false}: {pacts: Pact[]; selected: DirectionName | null; onSelect: (value: DirectionName | null) => void; loading?: boolean}) {
  const vertices = [0,3,4,5,2,1].map(index => directionPoint(directions[index].angle, 205));
  const polygon = vertices.map(point => `${point.x},${point.y}`).join(" ");
  return <div className="home-direction-map" role="group" aria-label="Направления пактов">
    <svg className="home-direction-lines" viewBox="0 0 640 640" preserveAspectRatio="none" fill="none" aria-hidden="true">
      <polygon points={polygon} className="home-hex-outline"/>
      <polygon points="320,157 461,239 461,401 320,483 179,401 179,239" className="home-hex-inner"/>
      {directions.map(item => {const point = directionPoint(item.angle,205);return <g key={item.id} style={{color:item.color}}><path d={`M320 320 L${point.x} ${point.y}`} className={selected === item.name ? "selected" : ""}/><circle cx={point.x} cy={point.y} r="7"/></g>;})}
    </svg>
    <svg className="home-direction-lines mobile-direction-lines" viewBox="0 0 640 640" preserveAspectRatio="none" fill="none" aria-hidden="true"><polygon points="320,58 498,192 498,448 320,582 142,448 142,192" className="home-hex-outline"/><polygon points="320,170 441,246 441,394 320,470 199,394 199,246" className="home-hex-inner"/></svg>
    <button className={"home-direction-center " + (selected === null ? "active" : "")} aria-pressed={selected === null} onClick={() => onSelect(null)} aria-controls="home-own-pacts"><span aria-hidden="true">念</span><strong>Все направления</strong></button>
    {directions.map(item => {
      const point = directionPoint(item.angle,205);
      const count = pacts.filter(pact => pact.status === "active" && directionOf(pact) === item.name).length;
      return <button key={item.id} data-direction={item.id} data-angle={item.angle} className={"home-direction-node " + (selected === item.name ? "active" : "")} aria-pressed={selected === item.name} aria-controls="home-own-pacts" style={{"--direction-color":item.color,left:point.x/6.4+"%",top:point.y/6.4+"%"} as CSSProperties} onClick={() => onSelect(item.name)}><span className="home-direction-glyph" aria-hidden="true">{item.glyph}</span><strong>{item.name}</strong><small>{loading ? "…" : `${count} / 12`}</small></button>;
    })}
  </div>;
}
