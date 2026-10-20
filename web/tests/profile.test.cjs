const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

let signedIn = true;
let apiPaths=[];
const loaded = new Map();
function load(relative) {
  const filename = path.join(__dirname, "../src/", relative);
  if (loaded.has(filename)) return loaded.get(filename);
  const compiled = ts.transpileModule(fs.readFileSync(filename, "utf8"), { compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, esModuleInterop: true } }).outputText;
  const compiledModule = { exports: {} };
  function localRequire(name) {
    if (name === "next/link") return { __esModule: true, default: ({ children, ...props }) => React.createElement("a", props, children) };
    if (name === "@/lib/api" || name === "./api") return { formatDate: () => "19 октября", localDay:()=>"2026-10-19",myPactsPath:()=>"/my/pacts?utc_offset_minutes=0",isExpired:pact=>pact.deadline === "expired",useApi:(path)=>{apiPaths.push(path);return {data:[],loading:false,error:null};},tiers: Object.fromEntries(["common","rare","epic","legendary"].map(tier=>[tier,{label:tier,duration:"7 дней"}])) };
    if (name === "@/lib/auth") return { useAuth: () => ({ user: signedIn ? { id: 1,username:"alice" } : null }) };
    if (name === "next/navigation") return {useRouter:()=>({push:()=>{},replace:()=>{}}),useSearchParams:()=>new URLSearchParams()};
    if (name === "@/lib/profile-navigation") return load("lib/profile-navigation.ts");
    if (name === "@/lib/community") return load("lib/community.ts");
    if (name === "@/lib/directions") return load("lib/directions.ts");
    if (name === "@/lib/profile-files") return load("lib/profile-files.ts");
    if (name.startsWith("@/lib/")) return load("lib/"+name.slice(6)+".ts");
    if (name === "./profile-editors") return {};
    if (name === "./ui" || name === "@/components/ui") return { Shell:({children})=>React.createElement("main",null,children),Icon: ({ name }) => React.createElement("svg", { "data-icon": name }), Action: ({ children, className, disabled }) => React.createElement("button", { className, disabled }, children),Modal:({title,children})=>React.createElement("section",{"data-modal":title},children),ErrorMessage:()=>null,Loading:()=>React.createElement("div",null,"Loading") };
    if (name.startsWith("@/components/")) return load("components/"+name.slice(13)+".tsx");
    if (name.startsWith("./")) {
      const base=path.resolve(path.dirname(filename),name);
      for(const suffix of [".tsx",".ts"]) if(fs.existsSync(base+suffix)) return load(path.relative(path.join(__dirname,"../src"),base+suffix));
    }
    return require(name);
  }
  new Function("require", "module", "exports", compiled)(localRequire, compiledModule, compiledModule.exports);
  loaded.set(filename, compiledModule.exports);
  return compiledModule.exports;
}
const { Achievements, YearGoals, ProfilePosts, FriendControls, Avatar } = load("components/profile-sections.tsx");
const { goalPercent } = load("lib/community.ts");
const render = (Component, props) => renderToStaticMarkup(React.createElement(Component, props));
const goal = { id: 7, year: new Date().getFullYear(), title: "12 books", description: "Read this year", target: 12, current: 3, unit: "книг", visibility: "private" };

test("goals show measured progress and expose edit controls only to their owner", () => {
  const publicHtml = render(YearGoals, { goals: [goal] });
  assert.match(publicHtml, /aria-valuenow="3"/);
  assert.match(publicHtml, /aria-valuemax="12"/);
  assert.match(publicHtml, /25%/);
  assert.doesNotMatch(publicHtml, /Добавить цель|Изменить цель|Удалить цель|>\+1</);
  const own = render(YearGoals, { goals: [goal], owner: true });
  assert.match(own, /Добавить цель/);
  assert.match(own, /Изменить цель/);
  assert.match(own, /Удалить цель/);
  assert.match(own, />\+1</);
});

test("completed goals disable the quick increment and percentages are bounded", () => {
  const html = render(YearGoals, { goals: [{ ...goal, current: 12 }], owner: true });
  assert.match(html, /disabled="">\+1</);
  assert.equal(goalPercent({ current: 12, target: 12 }), 100);
  assert.equal(goalPercent({ current: 2, target: 3 }), 67);
  assert.equal(goalPercent({ current: 20, target: 10 }), 100);
  assert.equal(goalPercent({ current: 1, target: 0 }), 0);
});

test("achievements display actual earned status and remaining requirements", () => {
  const items = [
    { id: "one", title: "First step", description: "One mark", count: 1, target: 1, earned: true, group: "path", tier: null },
    { id: "five", title: "Five common", description: "Five marked pacts", count: 3, target: 5, earned: false, group: "tier", tier: "common" },
  ];
  const html = render(Achievements, { items });
  assert.match(html, /achievement earned/);
  assert.match(html, /achievement locked/);
  assert.match(html, /1 \/ 2/);
  assert.match(html, /В процессе · 3 \/ 5/);
  assert.match(html, /data-tier="common"/);
});

test("curated media has a real image and safe outbound link, without automatic playback", () => {
  const post = { id: 3, kind: "music", title: "Album", content: "My inspiration", url: "https://example.org/music", visibility: "friends", image_url: "/api/v1/profile/posts/3/image", created_at: "2026-10-19", updated_at: "2026-10-19" };
  const html = render(ProfilePosts, { posts: [post] });
  assert.match(html, /href="https:\/\/example.org\/music" target="_blank" rel="noopener noreferrer"/);
  assert.match(html, /src="\/api\/v1\/profile\/posts\/3\/image"/);
  assert.match(html, /My inspiration/);
  assert.doesNotMatch(html, /iframe|autoplay|Удалить публикацию|Изменить публикацию/);
  assert.match(render(ProfilePosts, { posts: [post], owner: true }), /Удалить публикацию/);
});

test("friend actions reflect the real relationship and sign-in state", () => {
  signedIn = true;
  assert.match(render(FriendControls, { username: "boris", relationship: { status: "none", id: null } }), /Добавить в друзья/);
  assert.match(render(FriendControls, { username: "boris", relationship: { status: "outgoing", id: 1 } }), /Отменить заявку/);
  const incoming = render(FriendControls, { username: "boris", relationship: { status: "incoming", id: 1 } });
  assert.match(incoming, /Принять в друзья/);
  assert.match(incoming, /Отклонить/);
  assert.match(render(FriendControls, { username: "boris", relationship: { status: "friends", id: 1 } }), /Вы друзья/);
  signedIn = false;
  assert.match(render(FriendControls, { username: "boris", relationship: { status: "none", id: null } }), /href="\/login"/);
  signedIn = true;
});

test("avatar uses the saved image or the person's own initial", () => {
  assert.match(render(Avatar, { person: { id: 1, username: "alice", full_name: "Alice", avatar_url: "/api/v1/people/alice/avatar" } }), /<img src="\/api\/v1\/people\/alice\/avatar"/);
  const empty = render(Avatar, { person: { id: 1, username: "alice", full_name: "Alice" } });
  assert.match(empty, />A</);
  assert.doesNotMatch(empty, /<img/);
});

test("one profile shares notes with visitors and adds private pacts only for its owner",()=>{
  const {ProfileTabs}=load("components/profile-tabs.tsx");
  const html=render(ProfileTabs,{current:"overview",onChange:()=>{},owner:true});
  assert.equal([...html.matchAll(/role="tab"/g)].length,5);
  assert.match(html,/id="profile-tab-overview" role="tab" aria-selected="true"/);
  assert.match(html,/aria-controls="profile-panel-feed"/);
  assert.match(html,/profile-tab-notes/);
  const publicHtml=render(ProfileTabs,{current:"overview",onChange:()=>{},owner:false});
  assert.match(publicHtml,/profile-tab-notes/);
  assert.doesNotMatch(publicHtml,/profile-tab-pacts/);
});

test("profile links preserve pact, query and tab while sharing one canonical address",()=>{
  const {profileHref}=load("lib/profile-navigation.ts");
  assert.equal(profileHref("alice"),"/people/alice");
  assert.equal(profileHref("alice","pact=8","#pacts"),"/people/alice?pact=8#pacts");
  assert.equal(profileHref("alice","?x=1&y=2","feed"),"/people/alice?x=1&y=2#feed");
  assert.equal(profileHref("a/b"),"/people/a%2Fb");
});

test("the unified profile gives owner management and never loads own pacts for a visitor",()=>{
  const {UserProfile}=load("components/user-profile.tsx");
  const data={user:{id:1,username:"alice",full_name:"Alice"},created_at:"2026-10-19",bio:"",accent:"crimson",goals:[],posts:[],pins:[],achievements:[],friend_count:0,friend_preview:[],friendship:{status:"self",id:null},notes:[]};
  apiPaths=[];
  const own=render(UserProfile,{data});
  assert.match(own,/Настройки/);
  assert.match(own,/profile-tab-pacts/);
  assert.match(own,/Карта пактов/);
  assert.ok(apiPaths.some(path=>path?.startsWith("/my/pacts?")));
  apiPaths=[];
  const visitor=render(UserProfile,{data:{...data,user:{id:2,username:"boris",full_name:"Boris"},friendship:{status:"none",id:null}}});
  assert.doesNotMatch(visitor,/Настройки|profile-tab-pacts|Отметить все/);
  assert.match(visitor,/Добавить в друзья/);
  assert.match(visitor,/Предложить пакт/);
  assert.ok(!apiPaths.some(path=>path?.startsWith("/my/pacts")));
});

test("pacts and history are closed initially with an accessible native disclosure",()=>{
  const {ProfilePactList}=load("components/profile-pact-list.tsx");
  const html=render(ProfilePactList,{pacts:[]});
  assert.match(html,/<details class="profile-pact-details"><summary>/);
  assert.doesNotMatch(html,/<details[^>]*\sopen/);
  assert.match(html,/Мои пакты \/ История/);
});

test("profile status is always in the identity header and music uses manual controls",()=>{
  const {ProfileAbout}=load("components/profile-about.tsx");
  const profile={user:{id:1,username:"alice",full_name:"Alice"},created_at:"2026-10-19",status_text:"Учусь быть последовательнее",status_audio:{name:"My track.mp3",url:"/api/v1/profile/files/9/content"},bio:"Biography",about:"Details",interests:"Music, Books",website:"javascript:alert(1)"};
  const html=render(ProfileAbout,{profile,owner:true,onEdit:()=>{}});
  assert.match(html,/Учусь быть последовательнее/);
  assert.match(html,/<audio controls="" preload="none"/);
  assert.doesNotMatch(html,/My track.mp3/);
  assert.match(html,/Музыка профиля/);
  assert.match(html,/Повторять трек бесконечно/);
  assert.match(html,/Подробнее/);
  assert.doesNotMatch(html,/autoplay|javascript:|<details|<dialog/);
});

const attachment=(id,kind="file")=>({id,post_id:1,name:kind+"-"+id,size:100,kind,media_type:"application/octet-stream",pinned:false,visibility:"private",url:`/api/v1/profile/files/${id}/content`,download_url:`/api/v1/profile/files/${id}/content?download=true`,created_at:"2026-10-19"});
test("images and audio belong to one post, with manual audio controls below its gallery",()=>{
  const post={id:1,kind:"post",title:"One post",content:"With pictures and music",visibility:"public",url:"",image_url:null,created_at:"2026-10-19",attachments:[attachment(1,"image"),attachment(2,"audio"),attachment(3)]};
  const html=render(ProfilePosts,{posts:[post]});
  assert.ok(html.indexOf('<img src="/api/v1/profile/files/1/content"')<html.indexOf("<audio"));
  assert.match(html,/<audio controls="" preload="none" src="\/api\/v1\/profile\/files\/2\/content"/);
  assert.match(html,/Документ 1/);
  assert.doesNotMatch(html,/file-3/);
  assert.doesNotMatch(html,/Форматы публикаций|autoplay|iframe|Закрепить/);
});

test("one and ten images share the feed controls and expose every photo in their gallery",()=>{
  const post={id:1,kind:"post",title:"Uniform post",content:"Text",visibility:"public",url:"",image_url:null,created_at:"2026-10-19"};
  for(const count of [0,1,4,10]) {
    const html=render(ProfilePosts,{posts:[{...post,attachments:Array.from({length:count},(_,index)=>attachment(index+1,"image"))}]});
    assert.match(html,/class="feed-post uniform-feed-post(?: text-only-post)?"/);
    assert.equal([...html.matchAll(/class="post-gallery-item"/g)].length,count);
    assert.match(html,/Написать комментарий/);
    assert.doesNotMatch(html,/Ещё картинки/);
  }
});

test("forum posts show their author and restrict edit controls to that author",()=>{
  const post={id:1,kind:"post",title:"Forum post",content:"Visible",visibility:"public",url:"",image_url:null,created_at:"2026-10-19",author:{id:2,username:"boris",full_name:"Boris",avatar_url:"/avatar"}};
  const other=render(ProfilePosts,{posts:[post],forum:true});
  assert.match(other,/href="\/people\/boris"/);
  assert.match(other,/Посты пользователей/);
  assert.doesNotMatch(other,/Изменить публикацию|Удалить публикацию/);
  const own=render(ProfilePosts,{posts:[{...post,author:{...post.author,id:1}}],forum:true});
  assert.match(own,/Изменить публикацию/);
});

test("activity filters offer all, friends and mine, with guest sign-in for personal scopes",()=>{
  const {ActivityFilters}=load("components/activity-filters.tsx");
  const guest=render(ActivityFilters,{current:"all",onChange:()=>{},signedIn:false});
  assert.match(guest,/Вся активность/);
  assert.match(guest,/Друзья/);
  assert.match(guest,/>Моя</);
  assert.equal([...guest.matchAll(/disabled=""/g)].length,2);
  assert.match(guest,/href="\/login"/);
  const member=render(ActivityFilters,{current:"friends",onChange:()=>{},signedIn:true});
  assert.equal([...member.matchAll(/aria-pressed="true"/g)].length,1);
  assert.doesNotMatch(member,/disabled=""|href="\/login"/);
});

test("pinned shelf accepts arbitrary files and compact view limits previews to four",()=>{
  const {PinnedFiles}=load("components/profile-files.tsx");
  const files=Array.from({length:10},(_,index)=>({...attachment(index+1),name:`Archive-${index+1}.zip`,pinned:true}));
  const html=render(PinnedFiles,{files,compact:true});
  assert.equal([...html.matchAll(/class="pinned-file-tile /g)].length,4);
  assert.match(html,/10\/10/);
  assert.match(html,/ZIP/);
  assert.doesNotMatch(html,/Добавить или настроить/);
});

test("post composer has one format and an unrestricted multiple-file picker",()=>{
  const {PostEditor}=load("components/post-editor.tsx");
  const html=render(PostEditor,{onClose:()=>{}});
  assert.match(html,/<input[^>]*type="file"[^>]*multiple=""/);
  assert.doesNotMatch(html,/accept=|Формат|name="kind"/);
  assert.match(html,/25 МиБ/);
});

test("achievement showcase uses four clickable visual previews instead of all detail rows",()=>{
  const items=Array.from({length:12},(_,index)=>({id:"award-"+index,title:"Achievement "+index,description:"Criterion",count:0,target:5,earned:false,group:"topic",tier:null}));
  const html=render(Achievements,{items,compact:true,onViewAll:()=>{}});
  assert.equal([...html.matchAll(/class="achievement-art"/g)].length,4);
  assert.match(html,/0 \/ 12/);
  assert.doesNotMatch(html,/Виды достижений/);
});

test("overview puts measured yearly goals first and uses real friend avatars",()=>{
  const {ProfileOverview}=load("components/profile-overview.tsx");
  const data={user:{id:1,username:"alice",full_name:"Alice"},goals:[goal],posts:[],pins:[],achievements:[],friend_count:1,friend_preview:[{id:2,username:"boris",full_name:"Boris",avatar_url:"/api/v1/people/boris/avatar"}]};
  const html=render(ProfileOverview,{data,owner:true,onNavigate:()=>{},onDirection:()=>{}});
  assert.ok(html.indexOf("overview-goals")<html.indexOf("pact-preview-body"));
  assert.match(html,/12 books/);
  assert.match(html,/25%/);
  assert.match(html,/href="\/people\/boris"/);
  assert.match(html,/src="\/api\/v1\/people\/boris\/avatar"/);
});

test("active pact list precedes the direction map and creation uses a separate friends action",()=>{
  const {default:Home}=load("app/page.tsx");
  const html=render(Home,{});
  assert.ok(html.indexOf('id="home-own-pacts"')<html.indexOf('class="home-pact-stage"'));
  assert.match(html,/class="home-context-actions"/);
  assert.match(html,/home-joint-action[^>]*><svg data-icon="friends"/);
});

test("filenames are absent from pins, media, inspectors and profile settings",()=>{
  const {PinnedFiles,AttachmentList,FileInspector}=load("components/profile-files.tsx");
  const {SettingsForm}=load("components/profile-editors.tsx");
  const files=['image','audio','video','file'].map((kind,i)=>({...attachment(i+1,kind),name:`private-original-${i}.dat`,pinned:true}));
  const profile={user:{id:1,username:'alice',full_name:'Alice'},bio:'',accent:'crimson',status_audio:files[1],status_audio_id:2};
  const html=render(PinnedFiles,{files,owner:true})+render(AttachmentList,{files,owner:true})+files.map(file=>render(FileInspector,{file,owner:true,onClose:()=>{}})).join('')+render(SettingsForm,{profile,onClose:()=>{}});
  for(const file of files)assert.ok(!html.includes(file.name),file.kind+' exposes its filename');
  assert.match(html,/Текущий трек/);assert.match(html,/Громкость/);assert.match(html,/Повторять трек бесконечно/);
});
