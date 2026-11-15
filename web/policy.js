'use strict';
fetch('/api/v2/auth/me').then(r=>r.json()).then(data=>{
  if(!data.support_contact)return;
  const area=document.querySelector('#support');area.textContent='Liên hệ: ';
  let url;try{url=new URL(data.support_contact);}catch{area.append(document.createTextNode(data.support_contact));return;}
  if(!['https:','mailto:'].includes(url.protocol)){area.append(document.createTextNode(data.support_contact));return;}
  const link=document.createElement('a');link.href=url.href;link.textContent=data.support_contact;link.rel='noopener noreferrer';area.append(link);
}).catch(()=>{});
