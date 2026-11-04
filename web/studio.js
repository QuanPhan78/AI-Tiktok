'use strict';
const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names = ['Sản phẩm','Tình huống','Nhân vật','Kế hoạch cảnh','Lời thoại','Tổng hợp','Xuất prompt'];
const stateNames = {awaiting_input:'Chờ tạo bản nháp',awaiting_approval:'Chờ bạn duyệt',processing:'Đang xử lý',ready:'Đã chốt bộ prompt',needs_changes:'Cần chỉnh sửa',error:'Chưa hoàn tất'};
let session = null, library = [], poll = null, busy = false, renderedStep = '';
async function api(path, options={}) {
  const r = await fetch('/api/v2'+path, options);
  const d = await r.json();
  if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail || d));
  return d;
}
function notice(message='') { $('#notice').hidden=!message; $('#notice').textContent=message; }
function toast(t) { $('#toast').textContent=t; $('#toast').hidden=false; setTimeout(()=>$('#toast').hidden=true,2400); }
function revealOutcome() {
  const target = !$('#notice').hidden ? $('#notice') : session?.step===6 ? $('#qc-result') : session?.step===7 ? $('#exports') : $('#editor');
  if (!target) return;
  target.setAttribute('tabindex','-1');
  target.focus({preventScroll:true});
  target.scrollIntoView({block:'start',behavior:'auto'});
}
function qcTarget(field) {
  if(field.startsWith('dialogues.'))return 'dialogue-row-'+field.split('.')[1];
  if(field.startsWith('publishing.captions.'))return 'caption-'+field.split('.')[2];
  if(field.startsWith('publishing.slogans.'))return 'slogans';
  if(field.startsWith('publishing.hashtags.'))return 'hashtags';
  return {'publishing.pinned_comment':'pinned','publishing.overlay_scene2':'overlay2','publishing.overlay_scene4':'overlay4'}[field]||'';
}
function qcReport(s) {
  const processing=s.status==='processing', problems=s.validation||[], details=s.validation_details||[];
  const blocked=s.status==='error'||s.status==='needs_changes';
  const score=s.quality?`<span class="qc-score">QC ${esc(s.quality.qc_score)}/10 · cần từ 8</span>`:'';
  const title=processing?'Đang kiểm tra phương án':blocked?'Chưa thể xuất prompt':s.quality?'Kết quả kiểm tra':'Kiểm tra trước khi xuất';
  let html=`<section id="qc-result" class="qc-result ${blocked?'qc-blocked':''}" tabindex="-1" role="${blocked?'alert':'status'}" aria-live="polite" aria-busy="${processing}"><div class="qc-heading"><h3>${title}</h3>${score}</div>`;
  if(processing) return html+'<p>Đang kiểm tra QC và dữ liệu. Kết quả sẽ xuất hiện tại đây; nội dung đã duyệt được giữ nguyên.</p></section>';
  if(s.error)html+=`<p class="qc-error">${esc(s.error)}</p>`;
  if(details.length)html+='<h4>Lỗi cần sửa</h4>'+details.map(issue=>`<div class="qc-issue"><strong>${esc(issue.label||issue.field)}</strong><p>${esc(issue.message)}</p><blockquote>${esc(issue.quote)}</blockquote>${qcTarget(issue.field)?`<button class="quiet" data-qc-target="${esc(qcTarget(issue.field))}">Xem nội dung cần sửa ↑</button>`:''}</div>`).join('');
  const detailed = new Set(details.map(i=>`${i.label}: ${i.message} — “${i.quote}”`));
  const remaining=problems.filter(p=>!detailed.has(p));
  if(remaining.length)html+='<div class="qc-error">'+remaining.map(p=>`<p>${esc(p)}</p>`).join('')+'</div>';
  if(s.quality?.feedback)html+=`<p class="helper">${esc(s.quality.feedback)}</p>`;
  const warnings=s.quality?.warnings||s.warnings||[];
  if(warnings.length)html+='<div class="qc-warnings"><strong>Lời nhắc · không tự chặn xuất</strong><ul>'+warnings.map(w=>`<li>${esc(w)}</li>`).join('')+'</ul></div>';
  if(!blocked&&!s.quality)html+='<p>Bấm chốt để kiểm tra QC. Chỉ chuyển sang Bước 7 khi điểm đạt yêu cầu, không còn lỗi chặn và dữ liệu hợp lệ.</p>';
  if(blocked)html+=s.status==='error'?'<p class="helper">Kiểm tra thông báo lỗi rồi thử chốt lại. Bản chỉnh sửa được giữ nguyên; chưa có nội dung nào được tự duyệt.</p>':'<p class="helper">Sửa đúng trường/cảnh được chỉ ra rồi bấm chốt lại. Lời thoại đã duyệt không được AI tự viết lại.</p>';
  return html+'</section>';
}
function text(id,label,value='',extra='') { return `<label for="${id}">${label}</label><input id="${id}" value="${esc(value)}" ${extra}>`; }
function area(id,label,value='',cls='') { return `<label for="${id}">${label}</label><textarea id="${id}" class="${cls}">${esc(value)}</textarea>`; }
const val = id => document.getElementById(id)?.value ?? '';
async function upload(input) {
  const file = input.files[0]; if (!file) return null;
  const form = new FormData(); form.append('file',file);
  return (await api('/assets',{method:'POST',body:form})).id;
}
function context() {
  if (!session) return '<div class="eyebrow">MỘT QUY TRÌNH CHUNG</div><h3>Ý tưởng rõ ràng.<br>Nhân vật nhất quán.</h3><p>Chuẩn bị nội dung cùng Bảo, chuyển dữ liệu có cấu trúc sang Long.</p><hr><p>Mỗi cảnh là một clip độc lập 8 giây. Ứng dụng này chuẩn bị prompt và dữ liệu; chưa tạo video.</p>';
  const p=session.product,c=session.approved['3']?.character;
  return `<div class="eyebrow">SẢN PHẨM ĐANG LÀM</div>${p.asset_id?`<img class="thumb" src="/api/v2/assets/${encodeURIComponent(p.asset_id)}" alt="Ảnh sản phẩm">`:''}<h3>${esc(p.name)}</h3><p>${esc(p.uses)}</p><b>${esc(p.price)}</b><p><a href="${esc(p.product_link)}" target="_blank" rel="noopener noreferrer">Xem sản phẩm ↗</a></p>${c?`<hr><div class="eyebrow">NHÂN VẬT ĐÃ CHỌN</div><img class="thumb portrait" src="${c.asset_id?'/api/v2/assets/'+encodeURIComponent(c.asset_id):'/api/v2/characters/'+c.id+'/image'}" alt="${esc(c.name)}"><h3>${esc(c.id)} · ${esc(c.name)}</h3><p>${esc(c.voice)}</p>`:''}<hr><p>Đã xong: ${Object.keys(session.approved).join(', ')||'Chưa có bước nào'}<br>Đang chờ: ${esc(session.pending_action)}</p><small>Mã: ${esc(session.request_id)}<br>Phiên bản: ${session.revision}</small>`;
}
function productForm(p={}) {
  return `${text('product-name','Tên sản phẩm',p.name,'required maxlength="300"')}${area('product-uses','Công dụng đã xác nhận',p.uses)}<div class="grid2">${text('product-price','Giá (giữ nguyên cách ghi)',p.price,'required')}${text('product-link','Link sản phẩm',p.product_link,'type="url" required')}</div><label for="product-image">Ảnh sản phẩm${p.asset_id?' · Đã có ảnh, chỉ chọn nếu muốn thay':''}</label><input id="product-image" type="file" accept="image/png,image/jpeg,image/webp"><p class="helper">PNG, JPEG hoặc WebP · tối đa 10 MB. Thông tin và ảnh này sẽ được dùng trong bộ bàn giao.</p>`;
}
async function refreshList() {
  const list = await api('/sessions');
  $('#sessions').innerHTML=list.length?list.map(s=>`<button data-session="${s.id}" class="${session?.id===s.id?'active':''}">${esc(s.product.name)}<small>Bước ${s.step}/7 · ${esc(stateNames[s.status]||s.status)}</small></button>`).join(''):'<p class="helper" style="padding:12px">Chưa có phiên nào.<br>Tạo nội dung đầu tiên của bạn.</p>';
}
async function openSession(id) {
  clearTimeout(poll); notice();
  session=await api('/sessions/'+encodeURIComponent(id));
  localStorage.setItem('studio-session',id); render(); await refreshList(); schedulePoll();
}
function schedulePoll() {
  clearTimeout(poll);
  if (session?.status==='processing') {
    const id=session.id;
    poll=setTimeout(async()=>{try{const s=await api('/sessions/'+id);if(session?.id!==id)return;session=s;render();if(s.status!=='processing'){await refreshList();revealOutcome();}schedulePoll();}catch(e){notice(e.message);revealOutcome();}},650);
  }
}
async function action(kind,data={}) {
  if(busy||!session||session.status==='processing')return;
  busy=true; notice();
  const sid=session.id;
  const submittedPublishing=kind==='approve'&&session.step===6?data.publishing:null;
  try {
    session=await api(`/sessions/${sid}/actions`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:kind,data,revision:session.revision,operation_id:crypto.randomUUID()})});
    render();schedulePoll();if(session.status!=='processing'){await refreshList();revealOutcome();}
  } catch(e) {
    notice(e.message);
    if(session?.id===sid){
      session=await api('/sessions/'+sid);
      if(submittedPublishing&&session.step===6){session.draft=submittedPublishing;delete session.quality;session.validation=[];session.validation_details=[];}
      render();schedulePoll();
    }
    revealOutcome();
  }
  finally {busy=false;}
}
function render() {
  const stepKey = session ? session.id+':'+session.step : 'new';
  if (stepKey!==renderedStep) { window.scrollTo(0,0); renderedStep=stepKey; }
  $('#context').innerHTML=context(); $('#history').hidden=!session;
  $('#page-title').textContent=session?session.product.name:'Từ sản phẩm đến câu chuyện';
  $('#subtitle').textContent=session?`Bước ${session.step}/7 · ${names[session.step-1]}`:'Bảy bước để chuẩn bị một bộ prompt nhất quán, sẵn sàng bàn giao.';
  $('#steps').innerHTML=names.map((n,i)=>`<li><button data-step="${i+1}" class="${session?.step===i+1?'current':session?.step>i+1?'done':''}" ${!session||i+1>=session.step||session.status==='processing'?'disabled':''}><b>${session?.step>i+1?'✓':i+1}</b>${n}</button></li>`).join('');
  const editor=$('#editor');
  if(!session){editor.innerHTML=`<span class="status">BẮT ĐẦU MỘT CÂU CHUYỆN</span><h2>Sản phẩm của bạn là gì?</h2><p class="helper">Cung cấp thông tin chắc chắn. Mọi gợi ý bổ sung đều chờ bạn xác nhận.</p><form id="create-form">${productForm()}<div class="actions"><button class="primary" type="submit">Tạo phiên làm việc →</button></div></form>`;return;}
  const s=session,d=s.draft,a=s.approved,step=s.step;
  let html=`<span class="status">${esc(stateNames[s.status]||s.status)}</span><h2>${step}. ${names[step-1]}</h2>`;
  if(step!==6){
    if(s.error)html+=`<div class="error">${esc(s.error)}</div>`;
    if(s.validation?.length)html+=`<div class="message">${s.validation.map(esc).join('<br>')}<br>Hãy quay lại bước tương ứng để sửa, hoặc chỉnh nội dung tổng hợp rồi kiểm tra lại.</div>`;
    if(step<7)for(const w of s.warnings||[])html+=`<div class="message">${esc(w)}</div>`;
  }
  if(step===1){
    html+=`<details><summary>Sửa thông tin đầu vào hoặc thay ảnh</summary>${productForm(s.product)}<button id="save-product" style="margin-top:16px">Lưu thông tin đầu vào</button></details>`;
    if(d)html+=`<p class="helper">${esc(d.link_read?.message||'Thông tin do người dùng nhập.')}</p>${area('summary','Tóm tắt sản phẩm',d.summary)}${area('description-en','Mô tả sản phẩm bằng tiếng Anh (dùng trong prompt)',d.product_description_en)}${area('suggestions','Bổ sung cần bạn kiểm tra (mỗi dòng một ý)',d.suggestions.join('\n'))}<label class="check"><input type="checkbox" id="confirm-facts">Tôi đã kiểm tra tóm tắt và các thông tin bổ sung ở trên.</label>`;
  } else if(step===2&&d){
    html+=`<p>Chọn hoàn cảnh kể chuyện phù hợp nhất với sản phẩm.</p><div class="choices">${d.items.map((x,i)=>`<label class="choice"><input name="situation" type="radio" value="${i}" ${i===0?'checked':''}><b>${i+1}. ${esc(x.title)}</b><small>${esc(x.reason)} · ${esc(x.emotion)}</small></label>`).join('')}</div>${text('custom-situation','Hoặc nhập tình huống của riêng bạn')}`;
  } else if(step===3&&d){
    const custom = d.character.asset_id ? d.character : {};
    html+=`<p>${esc(d.reason)}</p><div class="characters">${library.map(c=>`<label class="character"><input type="radio" name="character" value="${c.id}" ${c.id===d.character.id?'checked':''}><img src="${c.image_url}" alt="${esc(c.name)}"><span>${esc(c.id)} · ${esc(c.name)}<br>${c.age} tuổi<small>${esc(c.voice)}<br>${esc(c.setting)}</small></span></label>`).join('')}</div><label for="audio-mode">Giọng nói trong video</label><select id="audio-mode"><option value="speaking" ${d.audio_mode!=='voiceover'?'selected':''}>Nhân vật nói trực tiếp</option><option value="voiceover" ${d.audio_mode==='voiceover'?'selected':''}>Không thoại trong clip, thuyết minh riêng khi dựng</option></select><p class="helper">Nhân vật dự phòng: ${esc(d.backup_id||'Bạn tự chọn')}. Bạn có thể chọn nhân vật khác bên trên.</p><details><summary>Tạo nhân vật mới (NV9 trở lên)</summary><label class="check"><input type="checkbox" id="custom-character" ${custom.asset_id?'checked':''}>Dùng nhân vật mới thay cho thư viện</label><div class="grid2">${text('char-id','Mã nhân vật',custom.id||'NV9')}${text('char-name','Tên nhân vật',custom.name)}</div><div class="grid2">${text('char-age','Tuổi',custom.age||'25','type="number" min="18" max="100"')}<div><label for="char-gender">Giới tính / đại từ</label><select id="char-gender"><option value="female">Nữ</option><option value="male" ${custom.gender==='male'?'selected':''}>Nam</option></select></div></div>${text('char-voice','Giọng nói',custom.voice)}${text('char-setting','Bối cảnh',custom.setting)}${text('char-outfit','Trang phục',custom.outfit)}${text('char-suitable','Loại sản phẩm phù hợp',custom.suitable_for)}${area('char-block','Khối nhân vật tiếng Anh, có chỗ điền [PRODUCT]',custom.consistency_block)}<label for="char-image">Ảnh nhân vật mới</label><input id="char-image" type="file" accept="image/png,image/jpeg,image/webp"></details>`;
  } else if(step===4){
    html+=`<label for="scene-count">Số cảnh cần tạo</label><select id="scene-count"><option value="4" ${d?.scenes.length===4?'selected':''}>4 cảnh · khoảng 32 giây trước khi cắt</option><option value="5" ${d?.scenes.length===5?'selected':''}>5 cảnh · tách công dụng thành 3A và 3B</option></select>`;
    if(d)html+=area('style-vi','Phong cách chung',d.style_vi)+text('lighting-en','Ánh sáng cố định (tiếng Anh)',d.lighting_en)+d.scenes.map((x,i)=>`<div class="scene"><div class="scene-heading"><h3>Cảnh ${x.id} · ${esc(x.part)}</h3><span>8 giây</span></div>${area('action-'+i,'Hành động',x.action_vi)}${area('idea-'+i,'Ý chính',x.idea_vi)}<details><summary>Mô tả dùng để lắp prompt</summary>${area('direction-'+i,'Mô tả cảnh bằng tiếng Anh',x.direction_en)}<label class="check"><input type="checkbox" id="visible-${i}" ${x.product_visible?'checked':''}>Sản phẩm xuất hiện trong cảnh</label></details></div>`).join('');
  } else if(step===5){
    const scene=a['4'].scenes[s.scene_cursor];
    html+=`<p class="helper">Đã duyệt ${Object.keys(s.dialogues).length} cảnh. Các lời thoại đã chốt được giữ nguyên.</p><h3>Cảnh ${scene.id} · ${esc(scene.part)}</h3><p>${esc(scene.action_vi)}</p>`;
    if(d)html+=area('dialogue','Lời thoại đang chờ duyệt',d.text)+'<p class="helper">Bạn có thể sửa trực tiếp rồi chốt cảnh này. Khoảng 20–26 từ là gợi ý; cần kiểm tra nhịp đọc trên clip thật.</p>';
  } else if(step===6&&d){
    html+='<h3>Bảng 1 · Lời thoại đã chốt</h3><table><thead><tr><th>Cảnh</th><th>Phần</th><th>Lời thoại</th></tr></thead><tbody>'+a['4'].scenes.map(x=>`<tr id="dialogue-row-${x.id}"><td>${x.id}</td><td>${esc(x.part)}</td><td>${esc(s.dialogues[x.id])}${x.id!=='4'?`<br><button class="quiet" data-dialogue="${x.id}">Sửa lời thoại cảnh này</button>`:''}</td></tr>`).join('')+'</tbody></table>';
    html+=`<h3>Bảng 2 · Nội dung để dựng và đăng bài</h3><table><tbody><tr><th>Slogan</th><td>${area('slogans','5 slogan, mỗi dòng một câu',d.slogans.join('\n'))}</td></tr><tr><th>Caption</th><td>${d.captions.map((c,i)=>area('caption-'+i,'Caption '+(i+1),c)).join('')}<label for="selected-caption">Caption dùng để bàn giao</label><select id="selected-caption">${d.captions.map((_,i)=>`<option value="${i}" ${i===d.selected_caption?'selected':''}>Caption ${i+1}</option>`).join('')}</select></td></tr><tr><th>Hashtag</th><td>${area('hashtags','8–10 hashtag',d.hashtags.join(' '))}</td></tr><tr><th>Bình luận ghim</th><td>${area('pinned','Giữ nguyên link sản phẩm',d.pinned_comment)}</td></tr><tr><th>Chữ thêm khi dựng</th><td>${text('overlay2','Cảnh 2 · tên và công dụng ngắn',d.overlay_scene2)}${text('overlay4','Cảnh cuối · giá',d.overlay_scene4,'readonly')}</td></tr></tbody></table><p class="helper">Chốt sẽ kiểm tra toàn bộ nội dung trước khi xuất prompt. QC không tự thay đổi lời thoại bạn đã duyệt.</p>`;
  } else if(step===7){
    const b=s.bundle;
    html+=`<p>Bộ prompt đã được lắp từ nội dung bạn duyệt. Tải ZIP để lấy cả ảnh sản phẩm và ảnh nhân vật.</p><div class="downloads" id="exports" tabindex="-1" aria-label="Tải gói đã duyệt">${['zip','json','markdown'].map(f=>`<a href="/api/v2/sessions/${s.id}/export/${f}">↓ ${f==='markdown'?'Markdown':f.toUpperCase()}</a>`).join('')}</div>`;
    for(const w of b.qc.warnings)html+=`<p class="helper">${esc(w)}</p>`;
    html+=b.scenes.map(x=>`<div class="scene"><div class="scene-heading"><h3>Cảnh ${x.id} · ${esc(x.part)}</h3><button class="quiet" data-copy="prompt-${x.id}">Sao chép</button></div><textarea readonly class="prompt" id="prompt-${x.id}">${esc(x.prompt_en)}</textarea>${b.character.audio_mode==='voiceover'?`<p>Lời thuyết minh riêng: ${esc(x.dialogue_vi)}</p>`:''}<p class="helper">${x.overlay_text?'Chữ khi dựng: '+esc(x.overlay_text):'Không chèn chữ trong clip sinh bởi AI.'}</p></div>`).join('');
    html+=`<details open><summary>Nội dung đăng bài</summary>${area('export-caption','Caption đã chọn',b.publishing.captions[b.publishing.selected_caption])}<button class="quiet" data-copy="export-caption">Sao chép caption</button>${area('export-tags','Hashtag',b.publishing.hashtags.join(' '))}<button class="quiet" data-copy="export-tags">Sao chép hashtag</button>${area('export-pinned','Bình luận ghim',b.publishing.pinned_comment)}<button class="quiet" data-copy="export-pinned">Sao chép bình luận</button><p>${b.publishing.slogans.map(esc).join(' · ')}</p></details>`;
    if(s.handoff)html+=`<div class="message">Long đã xác nhận nhận bản ${s.handoff.revision}. Trạng thái nội dung là DRAFT, chưa phải video được duyệt đăng.</div>`;
  }
  if(step===6)html+=qcReport(s);
  if(step<7){html+=`<div class="question">${['Thông tin sản phẩm này đã đúng chưa?','Bạn chọn tình huống nào?','Bạn có đồng ý nhân vật và giọng nói này không?','Bạn có đồng ý kế hoạch các cảnh này không?','Bạn đã chốt lời thoại cảnh này chưa?','Bạn có chốt phương án cuối cùng này không?'][step-1]}</div><div class="actions"><button id="generate">${d?'Tạo lại bản nháp':'Tạo bản nháp'}</button>${d?`<button id="approve" class="primary">${step===6?'Chốt và xuất prompt →':step===5?'Chốt cảnh này →':'Đồng ý và tiếp tục →'}</button>`:''}</div>`;}
  else html+='<div class="actions"><button id="handoff" class="primary">Gửi sang Long →</button><span class="helper">Chỉ gửi bộ nội dung đã chốt.</span></div>';
  if(s.status==='processing')html+='<p class="busy"><span class="spinner"></span> Đang xử lý nội dung. Bạn có thể đóng trang và quay lại.</p>';
  editor.innerHTML=html;
  if(step===7)editor.querySelectorAll('textarea').forEach(e=>e.readOnly=true);
  if(s.status==='processing')editor.querySelectorAll('button,input,textarea,select').forEach(e=>e.disabled=true);
}
async function approve() {
  const d=session.draft,step=session.step; let data={};
  if(step===1){if(!$('#confirm-facts').checked)throw new Error('Hãy xác nhận bạn đã kiểm tra thông tin.');data={summary:val('summary'),suggestions:val('suggestions').split('\n').filter(Boolean),product_description_en:val('description-en')};}
  if(step===2)data={index:Number($('input[name=situation]:checked')?.value),custom:val('custom-situation').trim()};
  if(step===3){data={character_id:$('input[name=character]:checked')?.value,audio_mode:val('audio-mode')};if($('#custom-character').checked){const asset_id=await upload($('#char-image'))||d.character.asset_id;if(!asset_id)throw new Error('Cần ảnh nhân vật mới.');data.new_character={id:val('char-id'),name:val('char-name'),age:Number(val('char-age')),gender:val('char-gender'),voice:val('char-voice'),setting:val('char-setting'),outfit:val('char-outfit'),suitable_for:val('char-suitable'),consistency_block:val('char-block'),image_filename:'',asset_id};}}
  if(step===4)data={plan:{style_vi:val('style-vi'),lighting_en:val('lighting-en'),scenes:d.scenes.map((x,i)=>({...x,action_vi:val('action-'+i),idea_vi:val('idea-'+i),direction_en:val('direction-'+i),product_visible:$('#visible-'+i).checked}))}};
  if(step===5)data={text:val('dialogue')};
  if(step===6)data={publishing:{...d,slogans:val('slogans').split('\n').filter(Boolean),captions:[0,1,2].map(i=>val('caption-'+i)),selected_caption:Number(val('selected-caption')),hashtags:val('hashtags').split(/\s+/).filter(Boolean),pinned_comment:val('pinned'),overlay_scene2:val('overlay2'),overlay_scene4:val('overlay4')}};
  await action('approve',data);
}
document.addEventListener('click',async e=>{
  try{
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.qcTarget){const target=document.getElementById(b.dataset.qcTarget);if(target){target.setAttribute('tabindex','-1');target.focus({preventScroll:true});target.scrollIntoView({block:'center',behavior:'auto'});}return;}
    if(b.dataset.session)return await openSession(b.dataset.session);
    if(b.dataset.step){if(confirm('Quay lại bước này sẽ hủy xác nhận các bước phụ thuộc phía sau. Lịch sử vẫn được lưu.'))await action('reopen',{step:Number(b.dataset.step)});return;}
    if(b.dataset.dialogue)return await action('reopen',{step:5,scene_id:b.dataset.dialogue});
    if(b.dataset.copy){await navigator.clipboard.writeText(val(b.dataset.copy));toast('Đã sao chép');return;}
    if(b.id==='new-session'){clearTimeout(poll);session=null;localStorage.removeItem('studio-session');notice();render();await refreshList();}
    if(b.id==='generate')await action('generate',session.step===4?{scene_count:Number(val('scene-count'))}:{});
    if(b.id==='approve')await approve();
    if(b.id==='handoff')await action('handoff');
    if(b.id==='save-product'){const image=await upload($('#product-image'));await action('revise',{product:{name:val('product-name'),uses:val('product-uses'),price:val('product-price'),product_link:val('product-link'),asset_id:image||session.product.asset_id}});}
    if(b.id==='history'){const events=await api(`/sessions/${session.id}/history`);$('#history-body').innerHTML=events.length?events.map(x=>`<div class="history-row"><b>${esc(x.operation.action)} · Bước ${x.snapshot.step}</b><br>${esc(new Date(x.created).toLocaleString('vi-VN'))} · phiên bản ${x.snapshot.revision}<details><summary>Xem nội dung đã lưu</summary><pre style="white-space:pre-wrap">${esc(JSON.stringify(x.snapshot,null,2))}</pre></details></div>`).join(''):'Chưa có thao tác nào.';$('#history-dialog').showModal();}
    if(b.id==='close-history')$('#history-dialog').close();
  }catch(err){notice(err.message);revealOutcome();}
});
document.addEventListener('submit',async e=>{if(e.target.id!=='create-form')return;e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;notice();try{const asset_id=await upload($('#product-image'));session=await api('/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:val('product-name'),uses:val('product-uses'),price:val('product-price'),product_link:val('product-link'),asset_id})});localStorage.setItem('studio-session',session.id);render();await refreshList();}catch(err){notice(err.message);b.disabled=false;}});
(async()=>{try{library=await api('/characters');render();await refreshList();const last=localStorage.getItem('studio-session');if(last){try{await openSession(last);}catch{localStorage.removeItem('studio-session');}}}catch(e){notice(e.message);}})();
