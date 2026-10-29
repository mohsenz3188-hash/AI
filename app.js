'use strict';
const $ = (id) => document.getElementById(id);
const state = {current: null, conversations: [], files: [], sending: false, page: 'chat', loading: 0};
let toastTimer;
function toast(message) { $('toast').textContent = message; $('toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('toast').hidden = true, 6500); }
function errorMessage(data) { return typeof data.detail === 'string' ? data.detail : 'داده‌های واردشده معتبر نیستند.'; }
async function api(path, options = {}) {
  const response = await fetch('/api' + path, {credentials: 'same-origin', ...options, headers: {'Content-Type': 'application/json', ...options.headers}});
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401) showLogin();
    throw new Error(errorMessage(data));
  }
  return response;
}
function element(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
async function copy(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
    else { const area = element('textarea', 'sr-only', text); document.body.append(area); area.select(); const ok = document.execCommand('copy'); area.remove(); if (!ok) throw new Error(); }
    toast('کپی شد.');
  } catch { toast('کپی خودکار ممکن نیست؛ متن را انتخاب و کپی کنید.'); }
}
function inline(parent, text) {
  const regex = /(`[^`\n]+`|\*\*[^*\n]+\*\*)/g; let last = 0;
  for (const match of text.matchAll(regex)) { parent.append(document.createTextNode(text.slice(last, match.index))); parent.append(element(match[0].startsWith('`') ? 'code' : 'strong', '', match[0].startsWith('`') ? match[0].slice(1, -1) : match[0].slice(2, -2))); last = match.index + match[0].length; }
  parent.append(document.createTextNode(text.slice(last)));
}
function markdown(parent, text) {
  parent.replaceChildren(); const blocks = text.split(/```/);
  blocks.forEach((part, i) => {
    if (i % 2) {
      const split = part.indexOf('\n'); const language = split < 0 ? '' : part.slice(0, split).trim(); const code = split < 0 ? part : part.slice(split + 1).replace(/\n$/, '');
      const box = element('div', 'code-block'); const bar = element('div', 'code-toolbar'); bar.append(element('span', '', language || 'code')); const btn = element('button', '', 'کپی کد'); btn.addEventListener('click', () => copy(code)); bar.append(btn); const pre = element('pre'); pre.append(element('code', '', code)); box.append(bar, pre); parent.append(box);
    } else {
      for (const paragraph of part.split(/\n\n+/)) { if (!paragraph.trim()) continue; const heading = paragraph.match(/^#{1,6}\s+(.+)$/); const node = element(heading ? 'h3' : 'p'); node.dir = 'auto'; inline(node, heading ? heading[1] : paragraph); parent.append(node); }
    }
  });
}
function addMessage(role, content) {
  const article = element('article', 'message ' + role); const head = element('div', 'message-head'); head.append(element('span', '', role === 'user' ? 'شما' : '✧ نوا')); const btn = element('button', 'text-button', 'کپی'); let raw = content; btn.addEventListener('click', () => copy(raw)); head.append(btn); const body = element('div', 'message-body'); markdown(body, content); article.append(head, body); $('messages').append(article);
  return {article, update(text) { raw = text; markdown(body, text); }};
}
function showLogin() { $('workspace').hidden = true; $('login-screen').hidden = false; }
async function refreshHistory() { state.conversations = await (await api('/conversations')).json(); renderHistory(); }
function renderHistory() {
  $('history').replaceChildren(); const query = $('search').value.toLocaleLowerCase();
  const rows = state.conversations.filter(x => x.title.toLocaleLowerCase().includes(query));
  if (!rows.length) $('history').append(element('p', 'empty-history', query ? 'گفتگویی پیدا نشد.' : 'اولین گفتگوی خودت را شروع کن.'));
  rows.forEach(row => { const btn = element('button', row.id === state.current ? 'selected' : '', row.title); btn.title = row.title; btn.addEventListener('click', () => openConversation(row.id).catch(e => toast(e.message))); $('history').append(btn); });
}
function conversationControls(show) { for (const id of ['rename-chat', 'export-chat', 'delete-chat']) $(id).hidden = !show; }
function page(name) {
  if (state.sending) { toast('اجازه بده پاسخ فعلی کامل شود.'); return false; }
  state.page = name; $('chat-page').hidden = name !== 'chat'; $('images-page').hidden = name !== 'images'; $('page-title').textContent = name === 'chat' ? 'فضای کار' : 'استودیوی تصویر'; conversationControls(name === 'chat' && Boolean(state.current));
  document.querySelectorAll('[data-page]').forEach(btn => btn.classList.toggle('active', btn.dataset.page === name)); $('sidebar').classList.remove('open');
  if (name === 'images') loadGallery().catch(e => toast(e.message));
  return true;
}
function newChat() { if (!page('chat')) return; state.loading++; state.current = null; state.files = []; renderFiles(); $('messages').replaceChildren(); $('messages').hidden = true; $('welcome').hidden = false; $('prompt').value = ''; conversationControls(false); renderHistory(); $('prompt').focus(); }
async function openConversation(id) {
  if (!page('chat')) return; const ticket = ++state.loading; const conv = await (await api('/conversations/' + id)).json();
  if (ticket !== state.loading || state.sending) return;
  state.current = id; $('messages').replaceChildren(); conv.messages.forEach(m => addMessage(m.role, m.content)); $('welcome').hidden = conv.messages.length > 0; $('messages').hidden = !conv.messages.length; conversationControls(true); renderHistory(); scrollMessages();
}
function scrollMessages() { $('messages').scrollTop = $('messages').scrollHeight; }
function setSending(busy) { state.sending = busy; $('send').disabled = busy; $('send').textContent = busy ? '…' : '↑'; $('prompt').disabled = busy; $('attach').disabled = busy; $('delete-chat').disabled = busy; $('rename-chat').disabled = busy; }
async function enterWorkspace() {
  const cfg = await (await api('/config')).json(); $('model').replaceChildren(); cfg.models.forEach(model => { const option = element('option', '', model); option.value = model; $('model').append(option); }); $('account-name').textContent = cfg.username;
  $('config-notice').hidden = cfg.text_ready && cfg.image_ready; $('config-notice').textContent = !cfg.text_ready ? 'سرویس متن هنوز متصل نیست. کلید API را در تنظیمات سرور وارد کنید.' : 'سرویس تصویر هنوز متصل نیست. کلید تصویر را در تنظیمات سرور وارد کنید.';
  await refreshHistory(); $('login-screen').hidden = true; $('workspace').hidden = false; $('password').value = ''; newChat();
}
$('login-form').addEventListener('submit', async event => { event.preventDefault(); const btn = event.submitter; btn.disabled = true; $('login-error').textContent = ''; try { await api('/login', {method: 'POST', body: JSON.stringify({username: $('username').value, password: $('password').value})}); await enterWorkspace(); } catch(e) { $('login-error').textContent = e.message; } finally { btn.disabled = false; } });
$('logout').addEventListener('click', async () => { if (state.sending) return toast('پس از پایان پاسخ خارج شوید.'); try { await api('/logout', {method: 'POST'}); state.current = null; state.files = []; $('messages').replaceChildren(); $('gallery').replaceChildren(); $('prompt').value = ''; $('image-prompt').value = ''; showLogin(); } catch(e) { toast(e.message); } });
$('new-chat').addEventListener('click', newChat);
$('search').addEventListener('input', renderHistory);
$('menu').addEventListener('click', () => $('sidebar').classList.add('open'));
$('close-menu').addEventListener('click', () => $('sidebar').classList.remove('open'));
document.querySelectorAll('[data-page]').forEach(btn => btn.addEventListener('click', () => page(btn.dataset.page)));
document.querySelectorAll('[data-prompt]').forEach(btn => btn.addEventListener('click', () => { $('mode').value = btn.dataset.mode; $('prompt').value = btn.dataset.prompt; $('prompt').focus(); }));
$('rename-chat').addEventListener('click', async () => { if (!state.current || state.sending) return; const title = window.prompt('نام تازهٔ گفتگو:'); if (!title?.trim()) return; try { await api('/conversations/' + state.current, {method: 'PATCH', body: JSON.stringify({title: title.trim()})}); await refreshHistory(); } catch(e) { toast(e.message); } });
$('delete-chat').addEventListener('click', async () => { if (!state.current || state.sending || !window.confirm('این گفتگو برای همیشه حذف شود؟')) return; try { await api('/conversations/' + state.current, {method: 'DELETE'}); newChat(); await refreshHistory(); } catch(e) { toast(e.message); } });
$('export-chat').addEventListener('click', () => { if (state.current) window.location.assign('/api/conversations/' + state.current + '/export'); });
function renderFiles() { $('attachments').replaceChildren(); state.files.forEach((file, index) => { const btn = element('button', '', file.name + ' ×'); btn.type = 'button'; btn.addEventListener('click', () => { if (state.sending) return; state.files.splice(index, 1); renderFiles(); }); $('attachments').append(btn); }); }
$('attach').addEventListener('click', () => $('file-input').click());
$('file-input').addEventListener('change', async () => {
  try { for (const file of $('file-input').files) { if (state.files.length >= 3) throw new Error('حداکثر سه فایل متنی مجاز است.'); if (file.size > 80000) throw new Error('فایل باید کمتر از ۸۰ کیلوبایت باشد.'); const text = new TextDecoder('utf-8', {fatal: true}).decode(await file.arrayBuffer()); if (text.includes('\0') || text.length > 20000) throw new Error('فقط فایل متنی UTF-8 تا ۲۰ هزار نویسه پذیرفته می‌شود.'); state.files.push({name: file.name.slice(0,160), text}); } } catch(e) { toast(e instanceof TypeError ? 'فایل باید متنی و با کدگذاری UTF-8 باشد.' : e.message); } finally { $('file-input').value = ''; renderFiles(); }
});
$('prompt').addEventListener('keydown', event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); $('chat-form').requestSubmit(); } });
$('chat-form').addEventListener('submit', async event => {
  event.preventDefault(); if (state.sending || !$('prompt').value.trim()) return;
  const message = $('prompt').value.trim(), attachments = [...state.files]; setSending(true); state.loading++;
  let assistant, userBubble, committed = false;
  try {
    if (!state.current) { const conv = await (await api('/conversations', {method: 'POST'})).json(); state.current = conv.id; conversationControls(true); }
    $('welcome').hidden = true; $('messages').hidden = false; userBubble = addMessage('user', message + (attachments.length ? '\n\nپیوست‌ها: ' + attachments.map(f => f.name).join('، ') : '')); assistant = addMessage('assistant', 'در حال فکر کردن…'); scrollMessages();
    const response = await api('/conversations/' + state.current + '/chat', {method: 'POST', body: JSON.stringify({message, attachments, mode: $('mode').value, model: $('model').value, language: $('language').value.trim() || 'فارسی'})});
    const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '', answer = '';
    while (true) {
      const {value, done} = await reader.read(); buffer += decoder.decode(value, {stream: !done}); const lines = buffer.split('\n'); buffer = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue; const item = JSON.parse(line);
        if (item.type === 'delta') { answer += item.text; assistant.update(answer); scrollMessages(); }
        else if (item.type === 'error') throw new Error(item.message);
        else if (item.type === 'done') committed = true;
      }
      if (done) break;
    }
    if (!committed) throw new Error('اتصال پیش از تکمیل پاسخ قطع شد. برای بررسی ذخیره‌شدن پاسخ، گفتگو را دوباره باز کنید.');
    $('prompt').value = ''; state.files = []; renderFiles(); await refreshHistory();
  } catch(e) { if (assistant && !committed) { assistant.update(e.message + '\n\nپیام در کادر پایین باقی مانده؛ می‌توانید دوباره ارسال کنید.'); assistant.article.classList.add('failed'); } toast(e.message); if (userBubble && !committed) userBubble.article.remove(); }
  finally { setSending(false); $('prompt').focus(); }
});
async function loadGallery() {
  const images = await (await api('/images')).json(); $('gallery').replaceChildren();
  if (!images.length) $('gallery').append(element('div', 'empty-gallery', 'گالری هنوز خالی است.\nاولین تصویرت را بساز.'));
  images.forEach(item => { const card = element('article', 'image-card'); const img = element('img'); img.src = '/api/images/' + item.id + '/file'; img.alt = item.prompt; img.loading = 'lazy'; const actions = element('div'); const link = element('a', '', 'دریافت تصویر ↓'); link.href = img.src; link.download = 'nava-image'; const remove = element('button', 'text-button danger', 'حذف'); remove.addEventListener('click', async () => { if (!window.confirm('این تصویر حذف شود؟')) return; try { await api('/images/' + item.id, {method: 'DELETE'}); await loadGallery(); } catch(e) { toast(e.message); } }); actions.append(link, remove); card.append(img, element('p', '', item.prompt), actions); $('gallery').append(card); });
}
$('image-form').addEventListener('submit', async event => {
  event.preventDefault(); const prompt = $('image-prompt').value.trim(); if (!prompt || $('generate').disabled) return; $('generate').disabled = true; $('image-status').textContent = 'در حال ساخت تصویر؛ این کار ممکن است چند دقیقه طول بکشد…';
  try { await api('/images', {method: 'POST', body: JSON.stringify({prompt, size: $('image-size').value})}); $('image-status').textContent = 'تصویر ساخته و در گالری ذخیره شد.'; await loadGallery(); } catch(e) { $('image-status').textContent = e.message; } finally { $('generate').disabled = false; }
});
enterWorkspace().catch(error => { showLogin(); if (error.message !== 'ابتدا وارد حساب شوید.') $('login-error').textContent = error.message; });
