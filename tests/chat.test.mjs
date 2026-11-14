import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const code = fs.readFileSync(new URL('../web/chat.js', import.meta.url), 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));
function deferred() { let resolve, reject; const promise = new Promise((a,b) => {resolve=a;reject=b;}); return {promise,resolve,reject}; }
function harness(fetch) {
  class Element {
    value=''; textContent=''; children=[]; events={}; disabled=false; hidden=false; scrollHeight=100;scrollTop=0;clientHeight=100;
    append(...items){this.children.push(...items);} replaceChildren(){this.children=[];}
    addEventListener(name,fn){this.events[name]=fn;} setAttribute(){} focus(){}
  }
  const elements = new Map(), storage = new Map();
  const select = key => { if (!elements.has(key)) elements.set(key,new Element());return elements.get(key); };
  select('#chat-mode').value='guide';
  const window={};
  vm.runInNewContext(code,{window,document:{querySelector:select,querySelectorAll:()=>[],createElement:()=>new Element()},
    localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
    fetch,crypto:{randomUUID:()=>crypto.randomUUID()},setTimeout:()=>1,clearTimeout:()=>{}});
  return {window,elements,select,storage};
}
const meta = id => ({id,revision:0,step:1,status:'awaiting_input',productName:id});
const data = (id, messages=[]) => ({session_id:id,revision:0,messages,next_before:null,config:{ai_enabled:false,daily_limit:20,used_today:0,reason:'Guide only'}});
const response = body => ({ok:true,json:async()=>body});

test('switching sessions ignores a late reply and preserves the draft for each session',async()=>{
  const late=deferred();
  const h=harness(url=>url.includes('/A/')?late.promise:Promise.resolve(response(data('B'))));
  h.window.ContentStudioChat.setSession(meta('A'));
  h.select('#chat-launcher').events.click();
  h.select('#chat-input').value='Bản nháp riêng của A';h.select('#chat-input').events.input();
  h.window.ContentStudioChat.setSession(meta('B'));
  await tick();
  late.resolve(response(data('A',[{seq:1,message_id:'a',text:'PRIVATE A',mode:'guide',revision:0,status:'done',reply:{answer:'PRIVATE A',sources:[],warnings:[]}}])));
  await tick();
  assert.equal(h.select('#chat-input').value,'');
  assert.ok(h.select('#chat-context').textContent.startsWith('B'));
  assert.ok(!JSON.stringify(h.select('#chat-messages').children).includes('PRIVATE A'));
  h.window.ContentStudioChat.setSession(meta('A'));
  assert.equal(h.select('#chat-input').value,'Bản nháp riêng của A');
});

test('an ambiguous send failure preserves text and retries the same message id',async()=>{
  const bodies=[];
  const h=harness(async(url,options={})=>{
    if (!options.method) return response(data('A'));
    bodies.push(JSON.parse(options.body));
    if(bodies.length===1) throw new Error('Connection interrupted');
    return response(data('A'));
  });
  h.window.ContentStudioChat.setSession(meta('A'));h.select('#chat-launcher').events.click();await tick();
  h.select('#chat-input').value='Câu hỏi giữ lại';h.select('#chat-input').events.input();
  h.select('#chat-form').events.submit({preventDefault(){}});await tick();
  assert.equal(h.select('#chat-input').value,'Câu hỏi giữ lại');
  assert.ok(h.select('#chat-error').textContent.includes('interrupted'));
  h.select('#chat-form').events.submit({preventDefault(){}});await tick();
  assert.equal(bodies.length,2);assert.deepEqual(bodies[0],bodies[1]);
  assert.equal(h.select('#chat-input').value,'');
});

test('AI text is rendered as text and cannot overwrite an existing draft during retry',async()=>{
  const turn={seq:1,message_id:'a',text:'Hỏi',revision:0,mode:'guide',status:'error',error:'Failed'};
  const h=harness(async()=>response(data('A',[turn])));
  h.window.ContentStudioChat.setSession(meta('A'));h.select('#chat-launcher').events.click();await tick();
  const reply=h.select('#chat-messages').children[0].children[1];
  h.select('#chat-input').value='<img src=x onerror=alert(1)>';
  reply.children.at(-1).events.click();
  assert.equal(h.select('#chat-input').value,'<img src=x onerror=alert(1)>');
  assert.ok(h.select('#chat-error').textContent.includes('bản nháp'));
  assert.ok(!code.includes('innerHTML'));
});
