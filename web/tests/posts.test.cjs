const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
let previewData=[],requestedPaths=[];

const loaded = new Map();
function load(relative) {
  const filename = path.join(__dirname,"../src",relative);
  if (loaded.has(filename)) return loaded.get(filename);
  const compiled = ts.transpileModule(fs.readFileSync(filename,"utf8"), {compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,esModuleInterop:true,target:ts.ScriptTarget.ES2020}}).outputText;
  const result = {exports:{}};
  function localRequire(name) {
    if(name==="next/link") return {__esModule:true,default:({children,...props})=>React.createElement("a",props,children)};
    if(name==="@/lib/api" || name==="./api") return {API_URL:"/api/v1",formatDate:()=>"20 октября",useApi:path=>{requestedPaths.push(path);return {data:path?.endsWith("?limit=3")?previewData:[],loading:false,error:null};}};
    if(name==="@/lib/auth") return {useAuth:()=>({user:{id:7,username:"alice"}})};
    if(name==="./ui") return {Icon:({name})=>React.createElement("svg",{"data-icon":name}),Action:({children})=>React.createElement("button",null,children),Modal:({title,children})=>React.createElement("section",{"data-modal":title},children),ErrorMessage:()=>null,Loading:()=>React.createElement("span",null,"Loading")};
    let base;
    if(name.startsWith("@/")) base=path.join(__dirname,"../src",name.slice(2));
    else if(name.startsWith(".")) base=path.resolve(path.dirname(filename),name);
    if(base) for(const suffix of [".tsx",".ts"]) if(fs.existsSync(base+suffix)) return load(path.relative(path.join(__dirname,"../src"),base+suffix));
    return require(name);
  }
  new Function("require","module","exports",compiled)(localRequire,result,result.exports);
  loaded.set(filename,result.exports);return result.exports;
}
const {inlineParts,safePostUrl,applyPostFormat}=load("lib/post-rich-text.ts");
const {galleryLayout}=load("lib/post-gallery.ts");
const {PostRichText}=load("components/post-rich-text.tsx");
const {AttachmentList}=load("components/profile-files.tsx");
const {FeedPost}=load("components/profile-feed.tsx");
const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props));
const attachment=id=>({id,post_id:1,name:`private-picture-${id}.png`,kind:"image",media_type:"image/png",size:100,pinned:false,visibility:"private",url:`/files/${id}`,download_url:`/files/${id}?download=true`});

test("post formatting renders a finite HTML-free vocabulary and rejects executable links",()=>{
  const html=render(PostRichText,{content:'**Слово** *курсив* ++линия++ ~~удалено~~ `код`\n> цитата\n- пункт\n[Сайт](https://example.org/a) <img src=x onerror=alert(1)> [x](javascript:alert(1))'});
  assert.match(html,/<strong>Слово<\/strong>/);assert.match(html,/<em>курсив<\/em>/);assert.match(html,/<u>линия<\/u>/);assert.match(html,/<s>удалено<\/s>/);assert.match(html,/<blockquote>/);
  assert.match(html,/href="https:\/\/example.org\/a"/);assert.match(html,/&lt;img/);assert.doesNotMatch(html,/<img|href="javascript:|onerror="/);
  for(const url of ["javascript:alert(1)","data:text/html,x","file:///secret","https://user:password@example.org","/relative"])assert.equal(safePostUrl(url),null);
  assert.equal(inlineParts("unformatted")[0].text,"unformatted");
});

test("toolbar formatting preserves surrounding text and returns selected text range",()=>{
  assert.deepEqual(applyPostFormat("до слово после",3,8,"**"),{value:"до **слово** после",start:5,end:10});
  assert.deepEqual(applyPostFormat("",0,0,"[","](https://example.org)","ссылка"),{value:"[ссылка](https://example.org)",start:1,end:7});
});

test("photo rows preserve every original ratio and fit the gallery budget without empty cells",()=>{
  for(let count=1;count<=11;count++){
    const original=Array.from({length:count},(_,i)=>[4/3,3/4,2.4,1,.4][i%5]);
    const layout=galleryLayout(original),gap=2,maxHeight=280;
    assert.deepEqual(layout.rows.flatMap(row=>row.indices),original.map((_,i)=>i));
    assert.deepEqual(layout.rows.flatMap(row=>row.ratios),original);
    const width=Math.min(360,(maxHeight+layout.gapAdjustment)*layout.aspect);
    const height=layout.rows.reduce((sum,row)=>sum+(width-(row.ratios.length-1)*gap)/row.ratios.reduce((a,b)=>a+b,0),0)+(layout.rows.length-1)*gap;
    assert.ok(height<=maxHeight+.001,`height budget for ${count} images`);
    for(const row of layout.rows){
      const rowHeight=(width-(row.ratios.length-1)*gap)/row.ratios.reduce((a,b)=>a+b,0);
      assert.ok(rowHeight>0);
      assert.ok(Math.abs(row.ratios.reduce((sum,ratio)=>sum+rowHeight*ratio,0)+(row.ratios.length-1)*gap-width)<.001);
    }
  }
  assert.deepEqual(galleryLayout([4/3,3/4,1.5]).rows.map(row=>row.indices),[[0],[1,2]]);
  assert.deepEqual(galleryLayout([3/4,3/4,3/4]).rows.map(row=>row.indices),[[0,1,2]]);
  assert.deepEqual(galleryLayout([]).rows,[]);
  assert.deepEqual(galleryLayout([NaN,0,Infinity]).rows.flatMap(row=>row.ratios),[4/3,4/3,4/3]);
});

test("post detail mounts every image immediately without filename headings, pin overlays or a hidden second page",()=>{
  const html=render(AttachmentList,{files:Array.from({length:10},(_,i)=>attachment(i+1)),owner:true});
  assert.equal((html.match(/<img /g)||[]).length,10);
  assert.equal((html.match(/loading="eager"/g)||[]).length,10);
  assert.doesNotMatch(html,/Ещё картинки|Свернуть картинки|<strong>private-picture|file-pin|Закрепить/);
  assert.match(html,/aria-label="Увеличить изображение 10"/);
});

test("feed shows the complete post, photos open directly, and only discussion has an open action",()=>{
  const html=render(FeedPost,{post:{id:1,kind:"post",title:"Мой пост",content:"**Текст**",url:"",visibility:"public",image_url:null,attachments:[attachment(1)],created_at:"2026-10-20",likes_count:4,comments_count:7,liked_by_me:true}});
  assert.match(html,/aria-label="Увеличить изображение 1"/);
  assert.doesNotMatch(html,/Открыть пост|Читать полностью|Читать пост полностью|feed-post-text clamped|private-picture-1/);
  assert.match(html,/aria-label="Убрать лайк" aria-pressed="true"/);assert.match(html,/>4<\/span>/);assert.match(html,/>7<\/span>/);
  assert.match(html,/<strong>Текст<\/strong>/);
});

test("feed comment preview requests three replies and never renders a fourth",()=>{
  previewData=Array.from({length:5},(_,i)=>({id:i+1,content:`Reply ${i+1}`,author:{username:"boris",full_name:"Boris"}}));
  requestedPaths=[];
  const html=render(FeedPost,{post:{id:8,title:"Post",content:"Visible text",created_at:"2026-10-20",visibility:"public",comments_count:5}});
  assert.ok(requestedPaths.includes("/profile/posts/8/comments?limit=3"));
  assert.match(html,/Reply 1/);assert.match(html,/Reply 3/);assert.doesNotMatch(html,/Reply 4|Reply 5/);
  assert.match(html,/Все комментарии · 5/);
  previewData=[];
});

function memoryStorage(){const data=new Map();return {getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,String(value)),removeItem:key=>data.delete(key)};}
function memoryIndexedDB(options={}){
  const values=new Map(Object.entries(options.seed??{}).map(([name,entries])=>[name,new Map(entries)]));
  return {values,open(){const request={};queueMicrotask(()=>{
    request.result={createObjectStore(){},close(){},transaction(names,mode){
      names=Array.isArray(names)?names:[names];
      const copies=new Map(names.map(name=>[name,new Map(values.get(name)??[])]));
      let pending=0,done=false;
      const tx={abort(){if(done)return;done=true;tx.onabort?.();}};
      function operation(action,write=false){
        const item={};pending++;
        queueMicrotask(()=>{
          if(done)return;
          if(write&&options.failWrites){tx.error=new Error("Quota exceeded");tx.abort();return;}
          item.result=action();item.onsuccess?.();pending--;
          queueMicrotask(()=>{if(!done&&!pending){done=true;if(mode==='readwrite')for(const [name,data] of copies)values.set(name,data);tx.oncomplete?.();}});
        });return item;
      }
      tx.objectStore=name=>({
        get:key=>operation(()=>copies.get(name).get(key)),
        put:(value,key)=>operation(()=>{options.puts?.push({store:name,files:Array.isArray(value)?value.length:value.files?.length??0});copies.get(name).set(key,value);},true),
        delete:key=>operation(()=>copies.get(name).delete(key),true),
      });return tx;
    }};request.onsuccess?.();
  });return request;}};
}
test("draft writes serialize before reopen and publish clearing; user/post keys isolate content and files",async()=>{
  const {postDraftKey,savePostDraft,loadPostDraft,deletePostDraft}=load("lib/post-drafts.ts");
  global.localStorage=memoryStorage();global.indexedDB=memoryIndexedDB();
  const key=postDraftKey(7),other=postDraftKey(8),edit=postDraftKey(7,11);
  assert.notEqual(key,other);assert.notEqual(key,edit);
  const file=new File(["image bytes"],"picture.png",{type:"image/png"});
  const draft={version:1,updatedAt:1,title:"Сохранено",content:"Текст",url:"",visibility:"private",retainedIds:[1],files:[file],removeImage:false,pinNew:false};
  const saving=savePostDraft(key,draft);
  assert.equal((await loadPostDraft(key)).title,"Сохранено");await saving;
  assert.equal(await (await loadPostDraft(key)).files[0].text(),"image bytes");assert.equal(await loadPostDraft(other),null);
  const a=savePostDraft(key,{...draft,content:"первая версия"});const b=savePostDraft(key,{...draft,content:"последняя версия"});
  await Promise.all([a,b]);assert.equal((await loadPostDraft(key)).content,"последняя версия");
  await deletePostDraft(key);assert.equal(await loadPostDraft(key),null);
});

test("if browser blob storage fails, draft text survives and saving files reports a warning",async()=>{
  const {postDraftKey,savePostDraft,loadPostDraft}=load("lib/post-drafts.ts");
  global.localStorage=memoryStorage();global.indexedDB=undefined;
  const key=postDraftKey(7,99),draft={version:1,updatedAt:1,title:"Текст не потерян",content:"Черновик",url:"",visibility:"private",retainedIds:[],files:[new File(["a"],"a.txt")],removeImage:false,pinNew:false};
  await assert.rejects(savePostDraft(key,draft),/Текст сохранён.*не смог сохранить файлы/);
  const recovered=await loadPostDraft(key);assert.equal(recovered.content,"Черновик");assert.deepEqual(recovered.files,[]);
});

test("quota failures recover newer fallback text even when IndexedDB can still read an old version",async()=>{
  const {postDraftKey,savePostDraft,loadPostDraft}=load("lib/post-drafts.ts");
  global.localStorage=memoryStorage();const options={failWrites:false};global.indexedDB=memoryIndexedDB(options);
  const key=postDraftKey(8,99),draft={version:1,updatedAt:1,title:"",content:"старая версия",url:"",visibility:"private",retainedIds:[],files:[],removeImage:false,pinNew:false};
  await savePostDraft(key,draft);options.failWrites=true;
  await assert.rejects(savePostDraft(key,{...draft,updatedAt:2,content:"новая версия",files:[new File(["a"],"a.txt")]}),/Текст сохранён/);
  const recovered=await loadPostDraft(key);assert.equal(recovered.content,"новая версия");assert.equal(recovered.missingFiles,true);
});

test("typing updates metadata without rewriting attachments; removing/discarding clears file records",async()=>{
  const {savePostDraft,loadPostDraft,deletePostDraft}=load("lib/post-drafts.ts");
  global.localStorage=memoryStorage();const options={puts:[]};global.indexedDB=memoryIndexedDB(options);
  const key='performance:files',file=new File(['unchanged original'],'original.bin'),files=[file];
  const draft={version:1,updatedAt:1,title:'',content:'',url:'',visibility:'private',retainedIds:[],files,removeImage:false,pinNew:false};
  for(let i=0;i<30;i++)await savePostDraft(key,{...draft,updatedAt:i+1,content:'a'.repeat(i)});
  assert.equal(options.puts.filter(p=>p.store==='attachments').length,1);
  assert.equal(options.puts.filter(p=>p.store==='drafts'&&p.files>0).length,0);
  const reopened=await loadPostDraft(key);
  assert.equal(await reopened.files[0].text(),'unchanged original');
  await savePostDraft(key,{...reopened,updatedAt:35,content:'Edited after reopening'});
  assert.equal(options.puts.filter(p=>p.store==='attachments').length,1);
  await savePostDraft(key,{...draft,updatedAt:40,files:[]});assert.equal((await loadPostDraft(key)).files.length,0);
  assert.equal(global.indexedDB.values.get('attachments').has(key),false);
  await savePostDraft(key,{...draft,updatedAt:50});await deletePostDraft(key);
  assert.equal(global.indexedDB.values.get('attachments').has(key),false);
});

test("immediate text checkpoint survives pending autosave and keeps already persisted files",async()=>{
  const {savePostDraft,checkpointPostDraft,loadPostDraft}=load("lib/post-drafts.ts");
  global.localStorage=memoryStorage();global.indexedDB=memoryIndexedDB();
  const key='performance:checkpoint',draft={version:1,updatedAt:1,title:'',content:'older',url:'',visibility:'private',retainedIds:[],files:[new File(['original'],'a.txt')],removeImage:false,pinNew:false};
  const pending=savePostDraft(key,draft);
  checkpointPostDraft(key,{...draft,updatedAt:2,content:'typed before older save completed'});
  await pending;const recovered=await loadPostDraft(key);
  assert.equal(recovered.content,'typed before older save completed');assert.equal(recovered.missingFiles,false);
  assert.equal(await recovered.files[0].text(),'original');
});

test("legacy drafts with embedded File blobs remain readable and normalize on the next save",async()=>{
  const {savePostDraft,loadPostDraft}=load("lib/post-drafts.ts");
  const key='performance:legacy',draft={version:1,updatedAt:1,title:'Legacy',content:'Kept',url:'',visibility:'private',retainedIds:[],files:[new File(['legacy bytes'],'old.txt')],removeImage:false,pinNew:false};
  global.localStorage=memoryStorage();global.indexedDB=memoryIndexedDB({seed:{drafts:[[key,draft]]}});
  const restored=await loadPostDraft(key);assert.equal(restored.title,'Legacy');assert.equal(await restored.files[0].text(),'legacy bytes');
  await savePostDraft(key,{...restored,updatedAt:2,content:'New text'});
  assert.equal((await loadPostDraft(key)).content,'New text');assert.equal(global.indexedDB.values.get('drafts').get(key).files.length,0);
});
