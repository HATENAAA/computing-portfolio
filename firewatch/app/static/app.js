const $ = id => document.getElementById(id);
let current = null, previewUrl = null;
const percent = n => (n * 100).toFixed(2) + '%';
function preview() {
  const f = $('file').files[0];
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  $('input-preview').hidden = !f;
  $('file-label').textContent = f ? f.name : '选择或拖入一张图像';
  if (f) { previewUrl = URL.createObjectURL(f); $('input-preview').src = previewUrl; }
}
$('file').addEventListener('change', preview);
$('brightness').addEventListener('input', e => $('brightness-value').value = e.target.value);
for (const event of ['dragover','dragleave','drop']) $('drop').addEventListener(event, e => {
  e.preventDefault(); $('drop').classList.toggle('drag', event === 'dragover');
  if (event === 'drop' && e.dataTransfer.files.length) {
    const transfer = new DataTransfer(); transfer.items.add(e.dataTransfer.files[0]);
    $('file').files = transfer.files; preview();
  }
});
function show(result) {
  current = result;
  $('result').hidden = false; $('empty').hidden = true;
  $('verdict').textContent = result.detected ? '疑似火焰' : '未触发规则';
  $('verdict').style.color = result.detected ? '#ca512d' : '#527347';
  $('area').textContent = percent(result.area_ratio);
  $('elapsed').textContent = result.elapsed_ms + ' ms';
  $('export').hidden = false; $('export').href = '/api/runs/' + result.id + '/report';
  $('methods').replaceChildren(...result.methods.map(m => {
    const row = document.createElement('tr');
    for (const text of [m.method, percent(m.edge_color_ratio), m.detected ? '疑似火焰' : '未触发']) {
      const cell=document.createElement('td');cell.textContent=text;row.append(cell);
    }
    return row;
  }));
  document.querySelectorAll('[data-view]').forEach(b => b.classList.toggle('active',b.dataset.view === 'overlay'));
  $('result-image').src = result.assets.overlay;
}
document.querySelectorAll('[data-view]').forEach(b => b.addEventListener('click', () => {
  if (!current) return;
  $('result-image').src = current.assets[b.dataset.view];
  document.querySelectorAll('[data-view]').forEach(x => x.classList.toggle('active',x === b));
}));
async function history() {
  const response = await fetch('/api/runs');
  if (!response.ok) throw new Error('读取历史记录失败');
  const rows = await response.json();
  if (!rows.length) { $('history-list').textContent='暂无记录'; return; }
  $('history-list').replaceChildren(...rows.map(run => {
    const button = document.createElement('button'); button.textContent=run.filename;
    const sub=document.createElement('small'); sub.textContent=new Date(run.created).toLocaleString()+' · '+(run.detected?'疑似火焰':'未触发规则');
    button.append(sub);button.addEventListener('click',()=>{show(run);$('status').textContent='已加载历史结果；重新分析时使用左侧当前参数。';});return button;
  }));
}
$('analyze-form').addEventListener('submit', async event => {
  event.preventDefault();
  const file=$('file').files[0];if (!file) return;
  if (file.size>10*1024*1024) { $('status').textContent='请选择小于 10 MB 的图片';return; }
  const data = new FormData(event.target);data.set('file',file);
  $('submit').disabled=true;$('status').textContent='正在分析图像…';
  try {
    const response=await fetch('/api/analyze',{method:'POST',body:data});
    const result=await response.json();
    if (!response.ok) throw new Error(typeof result.detail==='string'?result.detail:'参数无效，请检查输入');
    show(result);$('status').textContent='分析完成，结果与参数已保存。';await history();
  } catch(error) { $('status').textContent=error.message || '分析失败'; }
  finally { $('submit').disabled=false; }
});
history().catch(e=>$('status').textContent=e.message);
