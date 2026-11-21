'use strict';
(() => {
  const $=s=>document.querySelector(s), dialog=$('#publishing-dialog'), content=$('#publishing-content');
  let epoch=0,current=null,video=null,capabilities=null,accountRows=[],creatorInfo=null,pendingOperation=null;
  const statusLabels={ATTACHED:'Chưa duyệt',APPROVED:'Đã duyệt',NEEDS_REVISION:'Cần sửa',PENDING_REVIEW:'Chờ duyệt Telegram',QUEUED:'Chờ bắt đầu gửi',SCHEDULED:'Đã đặt lịch',INITIATING:'Đang gửi',PROCESSING:'TikTok đang xử lý',PUBLISHED:'TikTok xác nhận đã đăng',CANCELLED:'Đã hủy',MISSED:'Quá giờ · cần chọn lại',BLOCKED:'Cần xử lý trước khi gửi',RECONCILE:'Cần đối chiếu · không tự gửi lại',FAILED:'Đăng thất bại'};
  function node(tag,text,cls){const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n;}
  function explainError(text){
    if(text==='TikTok: unaudited_client_can_only_post_to_private_accounts'||text==='unaudited_client_can_only_post_to_private_accounts')return 'TikTok yêu cầu tài khoản ở chế độ riêng tư vì ứng dụng đang thử nghiệm. Chỉ chọn “Chỉ mình tôi” cho video chưa đủ. Trong TikTok, mở Hồ sơ → ☰ → Cài đặt và quyền riêng tư → Quyền riêng tư → Tài khoản riêng tư. Thay đổi này áp dụng cho toàn bộ tài khoản; bạn có thể dùng tài khoản thử riêng nếu muốn giữ tài khoản hiện tại công khai. Sau khi xử lý, đổi giờ của lượt đang bị chặn để thử lại. Mã lỗi: '+text;
    return text;
  }
  function msg(text='',error=false){$('#publishing-message').textContent=error?explainError(text):text;$('#publishing-message').className=error?'error':'';}
  async function api(path,method='GET',body){const r=await fetch('/api/v2'+path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Dữ liệu chưa hợp lệ.');return d;}
  function button(label,handler,disabled=false){const b=node('button',label);b.type='button';b.disabled=disabled;b.onclick=async()=>{b.disabled=true;msg();try{await handler();}catch(e){msg(e.message,true);}finally{b.disabled=disabled;}};return b;}
  function field(parent,id,label,type,value=''){const l=node('label',label);l.htmlFor=id;const n=node(type==='textarea'?'textarea':type==='select'?'select':'input');n.id=id;if(type!=='textarea'&&type!=='select')n.type=type;n.value=value;parent.append(l,n);return n;}
  function check(parent,id,label,checked=false){const l=node('label',null,'check'),n=node('input');n.id=id;n.type='checkbox';n.checked=checked;l.append(n,node('span',label));parent.append(l);return n;}
  function option(select,value,label){const o=node('option',label);o.value=value;select.append(o);}
  function timeVN(unix){return new Date(unix*1000).toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh'});}
  function isoVN(value){if(!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value))throw new Error('Chọn đủ ngày và giờ Việt Nam.');return value+':00+07:00';}
  async function open(sid=null){
    const token=++epoch;current=null;video=null;creatorInfo=null;pendingOperation=null;content.replaceChildren();msg('Đang đọc dữ liệu…');if(!dialog.open)dialog.showModal();
    if(sid){const loaded=await api('/sessions/'+sid);if(token!==epoch)return;current=loaded;renderVideo(token);}
    const section=node('section',null,'pub-card');content.append(section);
    try{const data=await api('/tiktok/accounts');if(token!==epoch)return;capabilities=data.capabilities;accountRows=data.accounts;renderAccounts(section);}
    catch(e){if(token===epoch){section.append(node('p',e.message));msg('Phần duyệt và lịch cần Automation đang chạy.',true);}return;}
    if(current)renderPost();
    else await renderOrdinary(token);
    const list=node('section',null,'pub-card');list.id='publication-list';content.append(list);await refreshJobs(list,token);if(token===epoch)msg(capabilities.ready&&capabilities.scheduler_enabled?'':capabilities.message);
  }
  async function renderOrdinary(token){
    const section=node('section',null,'pub-card');content.append(section);section.append(node('h3','Video thường đã hoàn chỉnh'),node('p','Dành cho MP4 không cần gắn giỏ hàng. Video từ quy trình 7 bước được mở bằng nút Đăng TikTok ở phiên tương ứng.'));
    const file=field(section,'ordinary-file','MP4 của bạn · tối đa 45 MB','file');file.accept='video/mp4';
    const caption=field(section,'ordinary-caption','Caption và hashtag','textarea');let operation=crypto.randomUUID().replaceAll('-','');
    file.onchange=()=>{operation=crypto.randomUUID().replaceAll('-','');};
    section.append(button('Tải video thường lên',async()=>{if(!file.files[0])throw new Error('Chọn MP4 trước.');if(file.files[0].size>45*1024*1024)throw new Error('MP4 tối đa 45 MB.');
      const form=new FormData();form.append('file',file.files[0]);form.append('caption',caption.value);form.append('operation_id',operation);
      const r=await fetch('/api/v2/publication-videos',{method:'POST',body:form}),d=await r.json();if(!r.ok)throw new Error(typeof d.detail==='string'?d.detail:'Chưa tải được video.');if(token!==epoch)return;await openOrdinary({...d,revision:1,version:1});}));
    const rows=await api('/publication-videos');if(token!==epoch)return;
    for(const row of rows)section.append(button((row.caption||'Video không có caption').slice(0,80)+' · '+statusLabels[row.status],()=>openOrdinary(row)));
  }
  async function openOrdinary(row){
    const token=++epoch;video=row;creatorInfo=null;pendingOperation=null;current={standalone:true,content_mode:'ordinary',id:row.id,product:{name:'Video thường'},video:{version:row.version,bundle_revision:row.revision},bundle:{revision:row.revision,scenes:[],publishing:{captions:[row.caption],selected_caption:0,hashtags:[]}}};
    content.replaceChildren();msg();const section=node('section',null,'pub-card');content.append(section);section.append(node('h3','Xem và duyệt đúng video'));
    const player=node('video');player.controls=true;player.preload='metadata';player.src='/api/v2/publication-videos/'+row.id+'/file';section.append(player);
    const watched=check(section,'pub-watched','Tôi đã xem hết video, kiểm tra nội dung và quyền sử dụng.');const state=node('p',statusLabels[row.status]);section.append(state);
    for(const [approve,label] of [[true,'Duyệt video này'],[false,'Video cần sửa']])section.append(button(label,async()=>{if(!watched.checked)throw new Error('Xem video và xác nhận trước khi duyệt.');const d=await api('/publication-videos/'+row.id+'/review','POST',{approve,watched:true,sha256:row.sha256});if(token!==epoch)return;video.status=d.status;state.textContent=statusLabels[d.status];}));
    const accounts=node('section',null,'pub-card');content.append(accounts);renderAccounts(accounts);
    renderPost();const list=node('section',null,'pub-card');list.id='publication-list';content.append(list);await refreshJobs(list,token);
  }
  function renderAccounts(parent){
    parent.append(node('h3','Tài khoản TikTok'));
    parent.append(node('p',capabilities.message,'pub-note'));
    if(capabilities.checks?.length){
      const list=node('ul');list.className='pub-setup';
      for(const check of capabilities.checks){const item=node('li',(check.ok?'✓ Đã cấu hình: ':'Cần hoàn tất: ')+check.label);if(!check.ok)item.append(node('p',check.action,'pub-note'));list.append(item);}
      parent.append(list);
    }
    if(capabilities.permission_note)parent.append(node('p',capabilities.permission_note,'pub-note'));
    if(capabilities.audited===false)parent.append(node('p','Ứng dụng đang thử nghiệm: TikTok yêu cầu cả tài khoản ở chế độ riêng tư và video chọn “Chỉ mình tôi”. Cài đặt tài khoản riêng tư ảnh hưởng toàn bộ tài khoản; hãy dùng tài khoản thử riêng nếu muốn giữ tài khoản hiện tại công khai.','pub-note'));
    if(!accountRows.some(a=>a.connected))parent.append(node('p','Chưa kết nối tài khoản TikTok. Bạn cần tự đăng nhập và cấp quyền cho tài khoản muốn đăng.'));
    parent.append(button('Kết nối tài khoản TikTok',async()=>{const d=await api('/tiktok/accounts/connect','POST');const u=new URL(d.url);if(u.origin!=='https://www.tiktok.com')throw new Error('Địa chỉ kết nối chưa hợp lệ.');location.assign(u.href);},!(capabilities.connect_ready??capabilities.ready)));
    for(const account of accountRows){const row=node('p',account.nickname+(account.connected?' · Đã kết nối':' · Đã ngắt'));if(account.connected)row.append(button('Ngắt kết nối',async()=>{if(!confirm('Ngắt tài khoản này và hủy các lịch chưa gửi?'))return;const d=await api('/tiktok/accounts/'+account.id,'DELETE');await open(current?.standalone?null:current?.id);if(!d.revoked_at_tiktok)msg('Đã ngắt tại Content Studio. TikTok chưa xác nhận thu hồi; kiểm tra quyền ứng dụng trong TikTok.');}));parent.append(row);}
  }
  function renderVideo(token){
    const s=current,v=s.video,b=s.bundle,section=node('section',null,'pub-card');content.append(section);
    section.append(node('h3',s.product.name),node('p',`Bộ prompt r${b?.revision} · MP4 v${v?.version||'—'}`));
    if(!v||v.bundle_revision!==b?.revision){section.append(node('p','Tải MP4 cho đúng bản nội dung đã duyệt trước.'));return;}
    const player=node('video');player.controls=true;player.preload='metadata';player.src=`/api/v2/sessions/${s.id}/videos/${v.version}`;section.append(player);
    const watched=check(section,'pub-watched','Tôi đã xem hết video: đúng nội dung, nhân vật và lời thoại.');
    const status=node('p','Chưa đọc trạng thái duyệt cho lịch đăng.');section.append(status);
    const actions=node('div',null,'pub-actions');section.append(actions);
    actions.append(button('Kiểm tra và đồng bộ MP4',async()=>{const row=await api('/sessions/'+s.id+'/publication','POST');if(token!==epoch)return;video=row;status.textContent='Trạng thái: '+(statusLabels[row.status]||row.status);updateReview();}));
    const reviewBox=node('div');section.append(reviewBox);
    function updateReview(){reviewBox.replaceChildren();if(!video||s.handoff){if(s.handoff)reviewBox.append(node('p','Phiên này dùng quyết định Telegram. Đồng bộ sẽ kiểm tra lại đúng MP4 đã gửi.'));return;}
      for(const [approve,label] of [[true,'Duyệt video này'],[false,'Video cần sửa']])reviewBox.append(button(label,async()=>{if(!watched.checked)throw new Error('Xem video và xác nhận đã xem trước khi duyệt.');const d=await api('/sessions/'+s.id+'/publication/review','POST',{approve,watched:true});if(token!==epoch)return;video.status=d.status;status.textContent='Trạng thái: '+statusLabels[d.status];}));
    }
  }
  function renderPost(){
    const token=epoch,s=current,b=s.bundle;if(!b||!s.video)return;
    const section=node('section',null,'pub-card');content.append(section);section.append(node('h3','Nội dung và giờ đăng'),node('p',s.content_mode==='ordinary'?'Video thường':'Video TikTok Shop · Chưa hỗ trợ đăng tự động'));
    const account=field(section,'pub-account','Đăng lên tài khoản','select');option(account,'','Chọn tài khoản TikTok');for(const a of accountRows.filter(a=>a.connected))option(account,a.id,a.nickname);
    const info=node('p','Chọn tài khoản để đọc quyền đăng hiện tại.','pub-note');section.append(info);
    const title=field(section,'pub-caption','Caption và hashtag','textarea',b.publishing.captions[b.publishing.selected_caption]+'\n'+b.publishing.hashtags.join(' '));
    const privacy=field(section,'pub-privacy','Ai có thể xem','select');option(privacy,'','Bạn tự chọn quyền riêng tư');
    const comments=check(section,'pub-comment','Cho phép bình luận'),duet=check(section,'pub-duet','Cho phép Duet'),stitch=check(section,'pub-stitch','Cho phép Stitch');
    const ai=check(section,'pub-ai','Gắn nhãn nội dung do AI tạo',true),commercial=check(section,'pub-commercial','Video quảng bá thương hiệu, sản phẩm hoặc dịch vụ');
    const disclosure=node('div');section.append(disclosure);disclosure.hidden=true;
    const branded=check(disclosure,'pub-branded','Quảng bá thương hiệu bên thứ ba / hợp tác thương hiệu'),organic=check(disclosure,'pub-organic','Quảng bá thương hiệu của tôi');
    const disclosureNote=node('p');disclosure.append(disclosureNote);
    const shopMention=s.content_mode!=='ordinary'||b.scenes.some(x=>(x.dialogue_vi||'').toLowerCase().includes('giỏ hàng'));
    if(shopMention)section.append(node('p','Đây là Video TikTok Shop. Bạn vẫn có thể xuất prompt, tạo và duyệt video; chưa hỗ trợ đăng tự động vì chưa tích hợp TikTok Shop. Muốn đổi loại, quay lại Bước 1 và duyệt lại nội dung.','error'));
    const noShop=check(section,'pub-no-shop','Tôi xác nhận video thực tế và nội dung đăng không cần gắn giỏ hàng TikTok Shop.');
    const consent=check(section,'pub-consent','Tôi đồng ý gửi đúng video và nội dung này tới tài khoản đã chọn, vào thời điểm đã xác nhận.');
    const terms=check(section,'pub-terms','Tôi đồng ý Music Usage Confirmation của TikTok và Branded Content Policy nếu là nội dung hợp tác thương hiệu.');
    const links=node('p');for(const [label,url] of [['Music Usage Confirmation','https://www.tiktok.com/legal/page/global/music-usage-confirmation/en'],['Branded Content Policy','https://www.tiktok.com/legal/page/global/bc-policy/en']]){const a=node('a',label+' ↗ ');a.href=url;a.target='_blank';a.rel='noopener noreferrer';links.append(a);}section.append(links);
    const when=field(section,'pub-time','Ngày giờ Việt Nam (UTC+7) · chỉ cần khi đặt lịch','datetime-local');
    account.onchange=async()=>{const selected=account.value;creatorInfo=null;privacy.replaceChildren();option(privacy,'','Bạn tự chọn quyền riêng tư');try{if(!selected)return;const data=await api('/tiktok/accounts/'+selected+'/creator');if(account.value!==selected||token!==epoch)return;creatorInfo=data;info.textContent=`Tài khoản: ${data.creator_nickname} · video tối đa ${data.max_video_post_duration_sec} giây`;
      if(token!==epoch)return;for(const p of data.privacy_level_options||[])option(privacy,p,{SELF_ONLY:'Chỉ mình tôi',PUBLIC_TO_EVERYONE:'Công khai',MUTUAL_FOLLOW_FRIENDS:'Bạn bè',FOLLOWER_OF_CREATOR:'Người theo dõi'}[p]||p);
      for(const [n,key] of [[comments,'comment'],[duet,'duet'],[stitch,'stitch']]){n.checked=false;n.disabled=!!data[key+'_disabled'];}
    }catch(e){msg(e.message,true);}};
    const actions=node('div',null,'pub-actions');section.append(actions);
    async function send(later){
      if(!video||video.status!=='APPROVED')throw new Error('Kiểm tra và đồng bộ MP4, rồi duyệt video trước khi đăng.');
      if(!creatorInfo||!privacy.value)throw new Error('Chọn tài khoản và quyền riêng tư.');
      if(!$('#pub-watched').checked||!consent.checked||!terms.checked||!noShop.checked)throw new Error('Kiểm tra và xác nhận đầy đủ video, quyền sử dụng và việc gửi đăng.');
      if(shopMention)throw new Error('Bộ kịch bản có lời kêu gọi bấm giỏ hàng. Chưa hỗ trợ tự đăng bộ này khi chưa tích hợp TikTok Shop.');
      if(commercial.checked&&!branded.checked&&!organic.checked)throw new Error('Chọn thương hiệu của bạn hoặc thương hiệu bên thứ ba.');
      const body={video_id:video.id,account_id:account.value,scheduled_at:later?isoVN(when.value):null,watched:true,consent:true,no_shop_required:true,post:{title:title.value,privacy_level:privacy.value,disable_comment:!comments.checked,disable_duet:!duet.checked,disable_stitch:!stitch.checked,is_aigc:ai.checked,brand_content_toggle:commercial.checked&&branded.checked,brand_organic_toggle:commercial.checked&&organic.checked}};
      const encoded=JSON.stringify(body);if(pendingOperation?.encoded!==encoded)pendingOperation={encoded,id:crypto.randomUUID()};
      await api('/publications','POST',{...body,operation_id:pendingOperation.id});pendingOperation=null;msg('Đã lưu lượt đăng. TikTok chưa được coi là đã đăng cho tới khi có kết quả xác nhận.');await refreshJobs($('#publication-list'),epoch);
    }
    const publishButtons=[button('Đăng ngay',()=>send(false),shopMention||!capabilities.ready||!capabilities.scheduler_enabled),button('Đặt lịch đăng',()=>send(true),shopMention||!capabilities.ready||!capabilities.scheduler_enabled)];actions.append(...publishButtons);
    if(shopMention||!capabilities.ready||!capabilities.scheduler_enabled)section.append(node('p',capabilities.message+' Video và bản nháp vẫn được giữ để tiếp tục sau.','pub-note'));
    function disclosureState(){disclosure.hidden=!commercial.checked;disclosureNote.textContent=branded.checked?'TikTok sẽ gắn nhãn Paid partnership. Không dùng quyền Chỉ mình tôi.':organic.checked?'TikTok sẽ gắn nhãn Promotional content.':'Chọn thương hiệu của bạn, bên thứ ba hoặc cả hai.';
      const invalid=commercial.checked&&(!branded.checked&&!organic.checked||branded.checked&&privacy.value==='SELF_ONLY');for(const b of publishButtons)b.disabled=shopMention||!capabilities.ready||!capabilities.scheduler_enabled||invalid;
    }commercial.onchange=branded.onchange=organic.onchange=privacy.onchange=disclosureState;
    section.append(node('p','Máy chủ cần bật và có mạng. TikTok có thể xử lý thêm sau giờ gửi. Lịch trễ quá 15 phút cần bạn xác nhận lại.','pub-note'));
  }
  async function refreshJobs(parent,token){
    const rows=await api('/publications');if(token!==epoch)return;parent.replaceChildren(node('h3','Lịch đăng của bạn'));parent.append(button('Cập nhật kết quả',()=>refreshJobs(parent,token)));
    if(!rows.length)parent.append(node('p','Chưa có lịch đăng.'));
    for(const row of rows){const card=node('article',null,'pub-card');card.append(node('strong',statusLabels[row.status]||row.status),node('p',timeVN(row.due)+' · giờ Việt Nam'),node('p',row.post.title,'pub-title'),node('small','Mã lượt: '+row.id));if(row.error)card.append(node('p',explainError(row.error),'error'));
      card.append(node('p',`${row.account_name||'TikTok'} · r${row.video?.revision||'—'} · MP4 v${row.video?.version||'—'}`));if(row.notion_sync_error)card.append(node('p',row.notion_sync_error,'pub-note'));
      if(row.status==='PUBLISHED'){
        card.append(node('p',row.post.privacy_level==='SELF_ONLY'?'Bài riêng tư đã được TikTok xác nhận.':'TikTok xác nhận đã đăng; bài công khai có thể cần thêm thời gian kiểm duyệt.'));
        card.append(node('p','TikTok đã xác nhận đăng. Hãy mở bài để kiểm tra hình và tiếng. Nếu bài không phát được, giữ mã lượt để đối chiếu; không tạo lượt đăng lại khi chưa rõ nguyên nhân.','pub-note'));
      }
      if(row.post_ids?.length)card.append(node('p','Mã bài TikTok: '+row.post_ids.join(', ')));
      if(['QUEUED','SCHEDULED','MISSED','BLOCKED'].includes(row.status)){
        const when=field(card,'job-time-'+row.id,'Đổi giờ Việt Nam','datetime-local');
        card.append(button('Đổi giờ',async()=>{await api('/publications/'+row.id+'/actions','POST',{version:row.version,action:'reschedule',scheduled_at:isoVN(when.value)});await refreshJobs(parent,token);}),button('Hủy lịch',async()=>{await api('/publications/'+row.id+'/actions','POST',{version:row.version,action:'cancel'});await refreshJobs(parent,token);}));
      }
      parent.append(card);
    }
  }
  $('#publishing-close').onclick=()=>{epoch++;dialog.close();};
  $('#show-publications').onclick=()=>open().catch(e=>msg(e.message,true));
  document.addEventListener('click',e=>{const b=e.target.closest('[data-publication-session]');if(b)open(b.dataset.publicationSession).catch(err=>msg(err.message,true));});
})();
