const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const source = fs.readFileSync(path.join(__dirname,"../src/lib/calendar.ts"),"utf8");
const compiled = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const calendarModule = {exports:{}};
new Function("require","module","exports",compiled)(require,calendarModule,calendarModule.exports);
const {periodFor,dayKey,parseDay,addDays,sortEntries,isOverdue} = calendarModule.exports;

test("month grid covers six full Monday-based weeks without changing the anchor",() => {
  const anchor = new Date(2026,9,19,12);
  const range = periodFor(anchor,"month");
  assert.equal(dayKey(range.start),"2026-09-28");
  assert.equal(dayKey(range.end),"2026-11-08");
  assert.equal(range.start.getDay(),1);
  assert.equal(dayKey(anchor),"2026-10-19");
});
test("weeks cross year boundaries and agenda respects leap-year month lengths",() => {
  const week = periodFor(new Date(2027,0,1,12),"week");
  assert.equal(dayKey(week.start),"2026-12-28");
  assert.equal(dayKey(week.end),"2027-01-03");
  assert.equal(dayKey(periodFor(new Date(2024,1,10),"agenda").end),"2024-02-29");
  assert.equal(dayKey(addDays(parseDay("2026-12-31"),1)),"2027-01-01");
});
test("plans sort by day, completion, time and priority without mutating API data",() => {
  const base = {kind:"task",day:"2026-10-19",completed:false,priority:"normal"};
  const entries = [{...base,id:1,start_time:"15:00"},{...base,id:2,start_time:"09:00",completed:true},{...base,id:3,start_time:"09:00"},{...base,id:4,start_time:"09:00",priority:"high"}];
  assert.deepEqual(sortEntries(entries).map(e => e.id),[4,3,1,2]);
  assert.deepEqual(entries.map(e => e.id),[1,2,3,4]);
});
test("only unfinished tasks can become overdue in the user's local time",() => {
  const now = new Date(2026,9,19,14,30);
  const task = {kind:"task",day:"2026-10-19",completed:false,start_time:"14:00"};
  assert.equal(isOverdue(task,now),true);
  assert.equal(isOverdue({...task,start_time:null},now),false);
  assert.equal(isOverdue({...task,completed:true},now),false);
  assert.equal(isOverdue({...task,kind:"event"},now),false);
  assert.equal(isOverdue({...task,day:"2026-10-20"},now),false);
});
