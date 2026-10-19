const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const helpers = {
  tiers:Object.fromEntries(["common","rare","epic","legendary"].map(tier => [tier,{label:tier}])),
  localDay:() => "2026-10-19", isExpired:pact => pact.deadline === "expired", formatDate:() => "26 октября",
};
let directions;
function load(relative) {
  const source = fs.readFileSync(path.join(__dirname,"../src/",relative),"utf8");
  const compiled = ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText;
  const compiledModule = {exports:{}};
  function localRequire(name) {
    if(name === "next/link") return {__esModule:true,default:({children,...props}) => React.createElement("a",props,children)};
    if(name === "@/lib/api" || name === "./api") return helpers;
    if(name === "@/lib/pact-progress" || name === "./pact-progress") return load("lib/pact-progress.ts");
    if(name === "@/lib/directions") return directions;
    if(name === "./pact-streak") return load("components/pact-streak.tsx");
    if(name === "./ui") return {Icon:() => React.createElement("svg"),Action:({children,className,disabled}) => React.createElement("button",{className,disabled},children)};
    return require(name);
  }
  new Function("require","module","exports",compiled)(localRequire,compiledModule,compiledModule.exports);
  return compiledModule.exports;
}
directions = load("lib/directions.ts");
const { PactSeal } = load("components/pact-seal.tsx");
const { HomeDirections } = load("components/home-directions.tsx");
const pact = id => ({id,title:"Pact "+id,description:"Commitment",rarity:"common",category:"Тело",status:"active",is_joint:false,template_id:"walk",duration_days:7,deadline:null,created_at:"2026-10-19T00:00:00Z",checkins:[],progress:0,members:[]});
const render = pacts => renderToStaticMarkup(React.createElement(PactSeal,{pacts}));
const ids = html => [...html.matchAll(/data-pact-id="(\d+)"/g)].map(match => Number(match[1]));

test("six fixed directions match the reference positions and do not invent pacts",() => {
  const html = render([]);
  for (const [id,angle] of [["body",-90],["social",-150],["discipline",150],["mind",-30],["creation",30],["other",90]]) {
    assert.match(html,new RegExp(`data-direction="${id}" data-angle="${angle}"`));
  }
  assert.deepEqual(ids(html),[]);
  assert.equal([...html.matchAll(/data-free-slot=/g)].length,0);
  assert.match(html,/念/);
  assert.match(html,/Нет активных пактов/);
  assert.doesNotMatch(html,/nen-heart|dagger|progressbar/);
  assert.match(html,/<div class="hex-core">.*?<small>нет пактов<\/small><\/div>/);
});

test("home polygon retains six directions, uses real active counts and an all-directions center",() => {
  const html = renderToStaticMarkup(React.createElement(HomeDirections,{pacts:[pact(1),{...pact(2),category:"Разум"},{...pact(3),status:"completed"}],selected:"Тело",onSelect:()=>{}}));
  for(const direction of directions.directions) assert.match(html,new RegExp(`data-direction="${direction.id}" data-angle="${direction.angle}"`));
  assert.equal([...html.matchAll(/data-count="1"/g)].length,2);
  assert.equal([...html.matchAll(/data-count="0"/g)].length,4);
  assert.doesNotMatch(html,/\/ 12/);
  assert.match(html,/Все направления/);
  assert.match(html,/念/);
  assert.doesNotMatch(html,/Каталог|Заключить готовый/);
});

test("search deep link selects its actual pact category and tier",() => {
  const html = renderToStaticMarkup(React.createElement(PactSeal,{pacts:[pact(1),{...pact(8),category:"Разум",rarity:"epic"}],initialPactId:8}));
  assert.match(html,/data-pact-id="8" aria-pressed="true"/);
  assert.doesNotMatch(html,/data-pact-id="1"/);
  assert.match(html,/Pact 8/);
});
test("the selected category and tier show exactly their real active IDs",() => {
  const html = render([pact(41),pact(13),{...pact(82),is_joint:true},{...pact(22),category:"Разум"},{...pact(29),rarity:"epic"},{...pact(1),status:"draft"},{...pact(2),status:"completed"}]);
  assert.deepEqual(ids(html),[13,41,82]);
  assert.match(html,/Совместный/);
  assert.equal([...html.matchAll(/data-free-slot=/g)].length,0);
  assert.match(html,/Тело, common: 3 пактов/);
});
test("tier selection defaults to an occupied tier rather than hiding a user's pact",() => {
  const html = render([{...pact(5),category:"Разум",rarity:"epic"}]);
  assert.deepEqual(ids(html),[5]);
  assert.match(html,/Разум, epic: 1 пактов/);
  assert.equal([...html.matchAll(/data-free-slot=/g)].length,0);
});
test("finite detail keeps actual progress separate from today's category completion",() => {
  const html = render([{...pact(1),progress:57,checkins:["2026-10-19"]}]);
  assert.match(html,/aria-valuenow="57"/);
  assert.match(html,/>57%<\/strong>/);
  assert.match(html,/data-today-progress="100"/);
  assert.match(html,/Отметить срыв/);
  assert.doesNotMatch(html,/Отметить сегодня/);
  const zero = render([pact(1)]);
  assert.match(zero,/aria-valuenow="0"/);
  assert.match(zero,/data-today-progress="0"/);
});
test("lifelong pacts show days and infinity without a fictional total percentage",() => {
  const html = render([{...pact(1),rarity:"legendary",duration_days:null,progress:null,checkins:["2026-10-17","2026-10-18"]}]);
  assert.match(html,/∞/);
  assert.match(html,/Дней соблюдения: 2/);
  assert.doesNotMatch(html,/progressbar|<strong>\d+%<\/strong>/);
});
test("unlimited pacts remain visible without obsolete slot constraints",() => {
  const html = render(Array.from({length:5},(_,index) => pact(index+1)));
  assert.deepEqual(ids(html),[1,2,3,4,5]);
  assert.doesNotMatch(html,/Лимит|из 3 мест|\/72|\/12|\/3/);
  assert.equal([...html.matchAll(/data-free-slot=/g)].length,0);
});

test("automatic daily state and totals use reported breaks rather than legacy checkins",() => {
  const auto={...pact(1),tracking_mode:"automatic",total_days:12,streak_days:8,broken_days:["2026-10-01"],last_break_on:"2026-10-01"};
  const broken={...auto,id:2,total_days:7,streak_days:0,broken_days:["2026-10-19"],last_break_on:"2026-10-19"};
  const summary=directions.directionSummary([auto,broken],"Тело");
  assert.equal(summary.checked,1);
  assert.equal(summary.eligible,2);
  assert.equal(summary.todayProgress,50);
  const html=render([broken]);
  assert.match(html,/Срыв отмечен сегодня/);
  assert.match(html,/>7<\/strong>/);
  assert.doesNotMatch(html,/Отметить сегодня|Сегодня отмечено/);
});
test("daily category progress excludes expired, inactive and capped unmarked pacts",() => {
  const input = [pact(1),{...pact(2),checkins:["2026-10-19"],progress:14},{...pact(3),deadline:"expired"},{...pact(4),duration_days:1,checkins:["2026-10-18"]},{...pact(5),status:"completed"}];
  const result = directions.directionSummary(input,"Тело");
  assert.equal(result.active.length,4);
  assert.equal(result.eligible,2);
  assert.equal(result.checked,1);
  assert.equal(result.todayProgress,50);
  assert.equal(result.counts.common,4);
  assert.equal(input[0].id,1);
});
test("legacy categories map consistently and directions remain independent",() => {
  assert.equal(directions.directionOf({...pact(1),category:"Здоровье"}),"Тело");
  assert.equal(directions.directionOf({...pact(1),category:"Развитие"}),"Разум");
  assert.equal(directions.directionOf({...pact(1),category:"unknown"}),"Другое");
  assert.equal(directions.directionOf({...pact(1),category:undefined,is_joint:true}),"Социум");
  const result = directions.directionSummary([pact(1),{...pact(2),rarity:"epic"},{...pact(3),category:"Разум"}],"Тело");
  assert.deepEqual(result.counts,{common:1,rare:0,epic:1,legendary:0});
});
