import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const code=fs.readFileSync(new URL('../web/publishing.js',import.meta.url),'utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const response=data=>({ok:true,json:async()=>data});
function harness(fetch){
 const elements=new Map(),events={};
 class Element{
  children=[];value='';checked=false;disabled=false;open=false;hidden=false;textContent='';
  set id(value){this._id=value;elements.set('#'+value,this);}get id(){return this._id;}
  append(...items){this.children.push(...items);}replaceChildren(...items){this.children=items;}
  showModal(){this.open=true;}close(){this.open=false;}
 }
 const get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id);};
 vm.runInNewContext(code,{document:{querySelector:get,createElement:()=>new Element(),addEventListener:(e,fn)=>events[e]=fn},fetch,
  URL,crypto:{randomUUID:()=>crypto.randomUUID()},location:{assign:()=>{}},confirm:()=>false});
 return {get,open:sid=>events.click({target:{closest:()=>({dataset:{publicationSession:sid}})}})};
}
const session=id=>({id,product:{name:id},video:{version:1,bundle_revision:26},bundle:{revision:26,scenes:[{dialogue_vi:'Ví dụ'}],publishing:{captions:['Bản nháp'],selected_caption:0,hashtags:[]}}});
const capabilities={ready:false,scheduler_enabled:false,message:'Cần cấu hình'};
test('late session response cannot overwrite the session selected later',async()=>{
 let finishA;const pending=new Promise(resolve=>finishA=resolve);
 const h=harness(url=>url.endsWith('/sessions/A')?pending:Promise.resolve(response(url.endsWith('/sessions/B')?session('B'):url.endsWith('/accounts')?{accounts:[],capabilities}:[])));
 h.open('A');h.open('B');await tick();await tick();finishA(response(session('A')));await tick();
 const text=JSON.stringify(h.get('#publishing-content').children);
 assert.ok(text.includes('B'));assert.ok(!text.includes('sessions/A'));
});
test('privacy has no default, interactions are unchecked, setup does not imply posting readiness',async()=>{
 const h=harness(url=>Promise.resolve(response(url.includes('/sessions/')?session('demo'):url.endsWith('/accounts')?{accounts:[],capabilities}:[])));
 h.open('demo');await tick();await tick();
 assert.equal(h.get('#pub-privacy').value,'');
 for(const id of ['#pub-comment','#pub-duet','#pub-stitch','#pub-consent','#pub-no-shop','#pub-commercial'])assert.equal(h.get(id).checked,false);
 const all=JSON.stringify(h.get('#publishing-content').children);
 assert.ok(all.includes('Cần cấu hình'));
});
