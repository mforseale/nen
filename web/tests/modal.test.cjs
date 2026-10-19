const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const ts=require("typescript");
const React=require("react");

// Exercise the shared component's real event handlers without a browser dependency.
const compiled=ts.transpileModule(fs.readFileSync(path.join(__dirname,"../src/components/ui.tsx"),"utf8"),{
  compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,esModuleInterop:true},
}).outputText;
const componentModule={exports:{}};
new Function("require","module","exports",compiled)(name=>{
  if(name==="react")return {...React,useRef:current=>({current}),useEffect:()=>{}};
  if(name==="./site-header" || name==="next/link")return {__esModule:true,default:()=>null};
  return require(name);
},componentModule,componentModule.exports);

function fixture(){
  let closes=0;
  const modal=componentModule.exports.Modal({title:"Edit profile",children:null,onClose:()=>{closes++;}});
  const dialog={getBoundingClientRect:()=>({left:100,top:100,right:700,bottom:700})};
  const input={type:"file"};
  const event=(target,x=150,y=150)=>({target,currentTarget:dialog,button:0,clientX:x,clientY:y,prevented:false,stopped:false,preventDefault(){this.prevented=true;},stopPropagation(){this.stopped=true;}});
  return {handlers:modal.props,dialog,input,event,closes:()=>closes};
}

test("canceling a native file picker preserves its parent editor, while dialog Escape closes normally",()=>{
  const f=fixture(),fileCancel=f.event(f.input);
  f.handlers.onCancel(fileCancel);
  assert.equal(f.closes(),0);
  assert.equal(fileCancel.prevented,false);
  assert.equal(fileCancel.stopped,true);
  const dialogCancel=f.event(f.dialog);
  f.handlers.onCancel(dialogCancel);
  assert.equal(f.closes(),1);
  assert.equal(dialogCancel.prevented,true);
});

test("a text selection released outside the dialog cannot dismiss the editor",()=>{
  const f=fixture();
  f.handlers.onPointerDown(f.event(f.input));
  f.handlers.onClick(f.event(f.dialog,730,150));
  assert.equal(f.closes(),0);
});

test("backdrop dismissal requires a click that starts and finishes outside without dragging",()=>{
  const f=fixture();
  f.handlers.onPointerDown(f.event(f.dialog,90,150));
  f.handlers.onClick(f.event(f.dialog,90,150));
  assert.equal(f.closes(),1);
  f.handlers.onClick(f.event(f.dialog,90,150));
  assert.equal(f.closes(),1,"a stale pointer press cannot dismiss again");
  f.handlers.onPointerDown(f.event(f.dialog,90,150));
  f.handlers.onClick(f.event(f.dialog,80,180));
  f.handlers.onPointerDown(f.event(f.dialog,90,150));
  f.handlers.onClick(f.event(f.dialog,150,150));
  f.handlers.onPointerDown(f.event(f.dialog,90,150));
  f.handlers.onPointerCancel();
  f.handlers.onClick(f.event(f.dialog,90,150));
  assert.equal(f.closes(),1);
});

test("a nested dialog's cancellation never dismisses its parent",()=>{
  const f=fixture(),nested=f.event({tagName:"DIALOG"});
  f.handlers.onCancel(nested);
  assert.equal(f.closes(),0);
  assert.equal(nested.stopped,true);
});
