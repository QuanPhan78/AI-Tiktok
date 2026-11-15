'use strict';
window.StudioAuth = {user:null,csrf:'',enabled:false};
(() => {
  const nativeFetch=window.fetch.bind(window), auth=window.StudioAuth;
  window.fetch=(url,options={})=>{
    const target=new URL(typeof url==='string'?url:url.url,location.href);
    if(target.origin===location.origin && target.pathname.startsWith('/api/v2/') && !['GET','HEAD','OPTIONS'].includes((options.method||'GET').toUpperCase())) {
      const headers=new Headers(options.headers||{});if(auth.csrf)headers.set('X-CSRF-Token',auth.csrf); options={...options,headers};
    }
    return nativeFetch(url,options);
  };
  async function request(path,body){const r=await fetch('/api/v2/auth/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Kiểm tra tên đăng nhập và mật khẩu (ít nhất 12 ký tự).');return d;}
  auth.ready=(async()=>{
    const r=await nativeFetch('/api/v2/auth/me');const data=await r.json();Object.assign(auth,data);
    const form=document.querySelector('#auth-form');
    if(form){
      const mode=document.querySelector('#auth-mode'),msg=document.querySelector('#auth-message');
      if(data.setup_required){mode.value='setup';document.querySelector('#setup-option').hidden=false;msg.textContent='Tạo tài khoản quản trị trực tiếp trên máy. Dữ liệu SEJOY hiện có sẽ thuộc tài khoản này.';}
      mode.onchange=()=>{document.querySelector('#recovery-field').hidden=mode.value!=='recover';};
      form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('button');button.disabled=true;msg.textContent='Đang xử lý…';try{
        const body={username:form.username.value,password:form.password.value};if(mode.value==='recover')body.recovery_code=form.recovery.value;
        const result=await request(mode.value,body);
        if(result.recovery_code){form.hidden=true;msg.textContent='Lưu mã khôi phục ở nơi riêng. Mã chỉ hiện một lần; không chia sẻ với người khác.';document.querySelector('#recovery-result').textContent=result.recovery_code;document.querySelector('#recovery-result').hidden=false;const next=document.querySelector('#auth-next');next.hidden=false;next.href=mode.value==='recover'?'/login':'/app';}
        else location.assign('/app');
      }catch(err){msg.textContent=err.message;}finally{button.disabled=false;}};
      return false;
    }
    if(data.enabled&&!data.user){location.assign('/login');return false;}
    auth.user=data.user||{id:'local',username:'Máy này',role:'admin'};
    const area=document.querySelector('#account-tools');
    if(area){const label=document.createElement('span');label.textContent=auth.user.username;area.append(label);
      if(data.enabled){const link=document.createElement('a');link.href='/account';link.textContent='Tài khoản';area.append(link);const button=document.createElement('button');button.textContent='Đăng xuất';button.className='quiet';button.onclick=async()=>{await request('logout',{});location.assign('/login');};area.append(button);}
    }
    return true;
  })().catch(()=>{const node=document.querySelector('#notice')||document.querySelector('#auth-message');if(node){node.hidden=false;node.textContent='Chưa kết nối được máy chủ. Tải lại trang để thử lại.';}return false;});
})();
