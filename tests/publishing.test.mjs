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

function buttons(element){return [element,...element.children.flatMap(buttons)].filter(x=>typeof x.onclick==='function');}
test('connection can be enabled while posting remains blocked and reasons are visible',async()=>{
 const setup={ready:false,connect_ready:true,scheduler_enabled:false,message:'Chưa thể đăng thật',
  checks:[{id:'media',ok:false,label:'Tên miền tải MP4',action:'Xác minh tên miền trước khi đăng'}],permission_note:'Cần kết nối từng tài khoản'};
 const h=harness(url=>Promise.resolve(response(url.includes('/sessions/')?session('demo'):url.endsWith('/accounts')?{accounts:[],capabilities:setup}:[])));
 h.open('demo');await tick();await tick();
 const root=h.get('#publishing-content');
 assert.equal(buttons(root).find(x=>x.textContent==='Kết nối tài khoản TikTok').disabled,false);
 for(const title of ['Đăng ngay','Đặt lịch đăng'])assert.equal(buttons(root).find(x=>x.textContent===title).disabled,true);
 assert.ok(JSON.stringify(root.children).includes('Xác minh tên miền trước khi đăng'));
 assert.ok(JSON.stringify(root.children).includes('Chưa kết nối tài khoản TikTok'));
});
test('failed posting preserves caption and retries the same operation',async()=>{
 const requests=[];let attempts=0;
 const h=harness((url,options={})=>{
  let data=[];
  if(url==='/api/v2/sessions/demo')data=session('demo');
  else if(url.endsWith('/accounts'))data={capabilities:{ready:true,connect_ready:true,scheduler_enabled:true},accounts:[{id:'abc',nickname:'Test',connected:true}]};
  else if(url.endsWith('/creator'))data={privacy_level_options:['SELF_ONLY'],creator_nickname:'Test',max_video_post_duration_sec:60};
  else if(url.endsWith('/publication'))data={id:'video',status:'APPROVED'};
  else if(url.endsWith('/publications')&&options.method==='POST'){
   requests.push(JSON.parse(options.body));attempts++;
   return Promise.resolve(attempts===1?{ok:false,json:async()=>({detail:'Mất kết nối, chưa xác nhận'})}:response({id:'job'}));
  }
  return Promise.resolve(response(data));
 });
 h.open('demo');await tick();await tick();
 await buttons(h.get('#publishing-content')).find(x=>x.textContent==='Kiểm tra và đồng bộ MP4').onclick();
 h.get('#pub-account').value='abc';await h.get('#pub-account').onchange();h.get('#pub-privacy').value='SELF_ONLY';
 for(const id of ['#pub-watched','#pub-consent','#pub-terms','#pub-no-shop'])h.get(id).checked=true;
 h.get('#pub-caption').value='Bản caption tôi đã sửa #demo';
 const submit=buttons(h.get('#publishing-content')).find(x=>x.textContent==='Đăng ngay');
 await submit.onclick();assert.equal(h.get('#pub-caption').value,'Bản caption tôi đã sửa #demo');
 assert.ok(h.get('#publishing-message').textContent.includes('Mất kết nối'));
 await submit.onclick();assert.equal(requests.length,2);assert.equal(requests[0].operation_id,requests[1].operation_id);
 assert.deepEqual(requests[0],requests[1]);
});
