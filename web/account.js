'use strict';
(async()=>{
  if(!await window.StudioAuth.ready)return;
  const $=s=>document.querySelector(s),msg=$('#notice');
  $('#account-name').textContent=window.StudioAuth.user.username;
  async function submit(form,path,method,body){const b=form.querySelector('button');b.disabled=true;try{
    const r=await fetch('/api/v2/auth/'+path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();
    if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Kiểm tra thông tin đã nhập.');
    form.reset();msg.textContent=d.deleted?(d.revoked_at_tiktok?'Đã xóa dữ liệu.':'Đã xóa dữ liệu trên máy chủ. Kiểm tra và thu hồi quyền ứng dụng trong TikTok.'):'Đã đổi mật khẩu. Đăng nhập lại để tiếp tục.';
    const a=document.createElement('a');a.href='/login';a.textContent=' Mở trang đăng nhập';msg.append(a);
  }catch(e){msg.textContent=e.message;}finally{b.disabled=false;}}
  $('#password-form').onsubmit=e=>{e.preventDefault();submit(e.target,'password','POST',{old_password:$('#old-password').value,new_password:$('#new-password').value});};
  $('#delete-form').onsubmit=e=>{e.preventDefault();if(confirm('Xóa vĩnh viễn dữ liệu Content Studio của tài khoản này?'))submit(e.target,'account','DELETE',{password:$('#delete-password').value,confirm_username:$('#delete-name').value});};
})();
