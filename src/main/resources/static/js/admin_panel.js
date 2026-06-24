(function () {
  async function apiGet(url) {
    const resp = await fetch(url);
    const json = await resp.json().catch(() => null);
    if (!resp.ok || (json && json.success === false)) {
      throw new Error((json && json.message) || ('请求失败: ' + resp.status));
    }
    return json;
  }

  async function apiPostForm(url, formObj) {
    const form = new URLSearchParams();
    Object.entries(formObj).forEach(([k, v]) => {
      if (v === undefined || v === null) return;
      form.append(k, String(v));
    });

    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString()
    });

    const json = await resp.json().catch(() => null);
    if (!resp.ok || (json && json.success === false)) {
      throw new Error((json && json.message) || ('请求失败: ' + resp.status));
    }
    return json;
  }

  async function apiPostMultipart(url, formData) {
    const resp = await fetch(url, {
      method: 'POST',
      body: formData
    });
    const json = await resp.json().catch(() => null);
    if (!resp.ok || (json && json.success === false)) {
      throw new Error((json && json.message) || ('请求失败: ' + resp.status));
    }
    return json;
  }

  function curUname() {
    const u = getCurrentUser();
    return u && u.uname ? u.uname : '';
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function safeHtml(s) {
    return (s ?? '').toString().replace(/[&<>"']/g, c => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[c]));
  }

  function normCol(s) {
    return (s ?? '').toString().trim().toLowerCase();
  }

  function setSelectOptions(selectEl, columns, placeholder) {
    if (!selectEl) return;
    const cols = Array.isArray(columns) ? columns : [];
    selectEl.innerHTML = '';

    const opt0 = document.createElement('option');
    opt0.value = '';
    opt0.textContent = placeholder || '（不映射）';
    selectEl.appendChild(opt0);

    for (const c of cols) {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      selectEl.appendChild(opt);
    }
  }

  function autoPick(selectEl, columns, candidates) {
    if (!selectEl) return;
    const cols = (columns || []).map(c => ({ raw: c, n: normCol(c) }));
    const cand = (candidates || []).map(normCol);
    for (const want of cand) {
      const hit = cols.find(x => x.n === want);
      if (hit) {
        selectEl.value = hit.raw;
        return;
      }
    }
    // 兜底：包含式匹配（例如 "Abstract" vs "abstract_text"）
    for (const want of cand) {
      const hit = cols.find(x => x.n.includes(want));
      if (hit) {
        selectEl.value = hit.raw;
        return;
      }
    }
  }

  function setStats(stats) {
    const grid = document.getElementById('statsGrid');
    if (!grid) return;

    const items = [
      { k: '用户数', v: stats.userCount },
      { k: '论文数（papers）', v: stats.paperCount },
      { k: '分析记录数（analysis_record）', v: stats.analysisCount },
      { k: '用户数据集期刊明细行数（user_journal_metrics）', v: stats.userJournalMetricsRows },
      { k: '关键词索引行数（user_keyword_occurrence）', v: stats.userKeywordOccurrenceRows },
      { k: '总库期刊指标行数（journal_metrics）', v: stats.journalMetricsRows }
    ];

    grid.innerHTML = '';
    for (const it of items) {
      const div = document.createElement('div');
      div.className = 'stat';
      div.innerHTML = `<div class="k">${it.k}</div><div class="v">${(it.v ?? 0)}</div>`;
      grid.appendChild(div);
    }
  }

  function renderUsers(users) {
    const tbody = document.getElementById('usersTbody');
    if (!tbody) return;

    tbody.innerHTML = '';

    for (const u of users) {
      const tr = document.createElement('tr');

      const uname = u.uname || '';
      const email = u.email || '';
      const isAdmin = !!u.isAdmin;
      const createdAt = u.createdAt || '';

      tr.innerHTML = `
        <td>${uname}</td>
        <td>${email}</td>
        <td>${isAdmin ? '是' : '否'}</td>
        <td>${createdAt}</td>
        <td>
          <div class="actions">
            <button class="btn btn-outline btn-sm" data-action="reset" data-uname="${uname}"><i class="fas fa-key"></i> 重置密码</button>
            <button class="btn btn-outline btn-sm" data-action="delete" data-uname="${uname}"><i class="fas fa-trash"></i> 删除</button>
          </div>
        </td>
      `;

      tbody.appendChild(tr);
    }

    tbody.querySelectorAll('button[data-action="reset"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const target = btn.getAttribute('data-uname');
        if (!target) return;
        const newPwd = window.prompt('请输入新密码（留空则生成随机密码，至少6位）:', '');
        try {
          const resp = await apiPostForm('/admin/users/reset-password', {
            uname: curUname(),
            targetUname: target,
            newPassword: newPwd || ''
          });
          const pwd = resp && resp.newPassword ? resp.newPassword : '';
          if (pwd) {
            window.alert('密码已重置，新密码为：\n\n' + pwd + '\n\n请妥善保存。');
          }
          showToast('密码已重置', 'success');
        } catch (e) {
          showToast(e.message || '重置失败', 'error');
        }
      });
    });

    tbody.querySelectorAll('button[data-action="delete"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const target = btn.getAttribute('data-uname');
        if (!target) return;
        if (!window.confirm(`确定删除用户 ${target} 吗？此操作不可恢复。`)) return;
        try {
          await apiPostForm('/admin/users/delete', {
            uname: curUname(),
            targetUname: target
          });
          showToast('用户已删除', 'success');
          await refresh();
        } catch (e) {
          showToast(e.message || '删除失败', 'error');
        }
      });
    });
  }

  // =========================
  // Papers import
  // =========================

  let lastPreviewColumns = [];
  let lastPreviewRowCount = 0;

  function fillMappingSelectors(columns) {
    const ids = [
      'map_title',
      'map_doi',
      'map_journal',
      'map_keywords',
      'map_publish_date',
      'map_abstract',
      'map_target'
    ];
    for (const id of ids) {
      setSelectOptions(byId(id), columns, '（不映射）');
    }

    autoPick(byId('map_title'), columns, ['title', 'ti', 'paper_title', 'document title', 'article title']);
    autoPick(byId('map_doi'), columns, ['doi', 'di', 'doi号', 'doi_url']);
    autoPick(byId('map_journal'), columns, ['journal', 'so', 'source title', '期刊']);
    autoPick(byId('map_keywords'), columns, ['keywords', 'de', 'author keywords', '关键词']);
    autoPick(byId('map_publish_date'), columns, ['publish_date', 'year', 'py', 'publication year', '发表年份']);
    autoPick(byId('map_abstract'), columns, ['abstract', 'ab', 'abstract_text', '摘要']);
    autoPick(byId('map_target'), columns, ['target', '研究领域', 'field']);
  }

  async function previewPapers() {
    const fileEl = byId('importFile');
    const formatEl = byId('importFormat');
    const hint = byId('importHint');
    const res = byId('importResult');

    if (!fileEl || !fileEl.files || fileEl.files.length === 0) {
      showToast('请选择文件', 'error');
      return;
    }

    const file = fileEl.files[0];
    const format = (formatEl && formatEl.value) ? formatEl.value : 'csv';

    const fd = new FormData();
    fd.append('uname', curUname());
    fd.append('format', format);
    fd.append('file', file);

    hint.textContent = '正在预览...';
    res.innerHTML = '';

    const json = await apiPostMultipart('/admin/papers/preview', fd);
    const columns = json.columns || [];
    const sample = json.sample || [];
    const rowCount = json.rowCount || 0;

    lastPreviewColumns = columns;
    lastPreviewRowCount = rowCount;
    fillMappingSelectors(columns);

    hint.textContent = `已读取 ${rowCount} 行，列数 ${columns.length}。请确认映射后点击导入。`;

    if (sample && sample.length > 0) {
      const show = sample.slice(0, 3).map(r => {
        const keys = Object.keys(r || {}).slice(0, 8);
        const obj = {};
        for (const k of keys) obj[k] = r[k];
        return obj;
      });
      res.innerHTML = `<div class="muted" style="margin-top:6px;">样例（前3行，截断显示）：</div><pre>${safeHtml(JSON.stringify(show, null, 2))}</pre>`;
    }
  }

  async function importPapers() {
    const fileEl = byId('importFile');
    const formatEl = byId('importFormat');
    const hint = byId('importHint');
    const out = byId('importResult');

    if (!fileEl || !fileEl.files || fileEl.files.length === 0) {
      showToast('请选择文件', 'error');
      return;
    }
    if (!lastPreviewColumns || lastPreviewColumns.length === 0) {
      if (!window.confirm('尚未预览映射，仍要继续导入吗？建议先点“预览并自动映射”。')) return;
    }

    const file = fileEl.files[0];
    const format = (formatEl && formatEl.value) ? formatEl.value : 'csv';

    const fd = new FormData();
    fd.append('uname', curUname());
    fd.append('format', format);
    fd.append('file', file);

    const maps = [
      'map_title', 'map_doi', 'map_journal', 'map_keywords',
      'map_publish_date', 'map_abstract', 'map_target'
    ];
    for (const id of maps) {
      const el = byId(id);
      if (el && el.value) fd.append(id, el.value);
    }

    const minYear = byId('minYear')?.value;
    const maxYear = byId('maxYear')?.value;
    const requireTitle = byId('requireTitle')?.checked;
    if (minYear) fd.append('minYear', minYear);
    if (maxYear) fd.append('maxYear', maxYear);
    fd.append('requireTitle', requireTitle ? 'true' : 'false');

    hint.textContent = '正在导入...';
    out.innerHTML = '';

    try {
      const json = await apiPostMultipart('/admin/papers/import', fd);
      const inserted = json.inserted ?? 0;
      const skipped = json.skipped ?? 0;
      const duplicates = json.duplicates ?? 0;
      const total = json.total ?? 0;

      hint.textContent = '';
      out.innerHTML = `
        <div class="stat" style="margin-top:10px;">
          <div class="k">导入结果</div>
          <div style="margin-top:8px;">总行数：<b>${total}</b></div>
          <div>新增入库：<b>${inserted}</b></div>
          <div>重复跳过：<b>${duplicates}</b></div>
          <div>筛选/缺失跳过：<b>${skipped}</b></div>
        </div>
      `;
      showToast('导入完成', 'success');
      await refresh();
    } catch (e) {
      hint.textContent = '';
      showToast(e.message || '导入失败', 'error');
    }
  }

  // =========================
  // Papers search
  // =========================

  let papersOffset = 0;

  function renderPapers(items, meta) {
    const tbody = byId('papersTbody');
    const metaEl = byId('papersMeta');
    if (!tbody) return;
    tbody.innerHTML = '';

    const total = meta?.total ?? 0;
    const limit = meta?.limit ?? 50;
    const offset = meta?.offset ?? 0;
    if (metaEl) {
      const from = total === 0 ? 0 : offset + 1;
      const to = Math.min(offset + limit, total);
      metaEl.textContent = `共 ${total} 条，当前 ${from}-${to}`;
    }

    for (const p of (items || [])) {
      const id = p.id ?? '';
      const doi = p.doi ?? '';
      const title = p.title ?? '';
      const journal = p.journal ?? '';
      const pd = p.publish_date ?? '';

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${safeHtml(id)}</td>
        <td>${safeHtml(doi)}</td>
        <td>${safeHtml(title)}</td>
        <td>${safeHtml(journal)}</td>
        <td>${safeHtml(pd)}</td>
        <td>
          <div class="actions">
            <button class="btn btn-outline btn-sm" data-action="detail" data-id="${safeHtml(id)}"><i class="fas fa-circle-info"></i> 详情</button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    }

    tbody.querySelectorAll('button[data-action="detail"]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = btn.getAttribute('data-id');
        if (!id) return;
        await showPaperDetail(id);
      });
    });
  }

  async function searchPapers(resetOffset) {
    if (resetOffset) papersOffset = 0;
    const q = byId('papersQuery')?.value || '';
    const limit = parseInt(byId('papersLimit')?.value || '50', 10) || 50;

    const url = '/admin/papers/search?uname=' + encodeURIComponent(curUname())
      + '&q=' + encodeURIComponent(q)
      + '&limit=' + encodeURIComponent(limit)
      + '&offset=' + encodeURIComponent(papersOffset);

    try {
      const json = await apiGet(url);
      renderPapers(json.items || [], { total: json.total, limit: json.limit, offset: json.offset });
    } catch (e) {
      showToast(e.message || '搜索失败', 'error');
    }
  }

  async function showPaperDetail(id) {
    try {
      const url = '/admin/papers/detail/' + encodeURIComponent(id) + '?uname=' + encodeURIComponent(curUname());
      const json = await apiGet(url);
      const paper = json.paper || {};

      const mask = byId('paperDetailMask');
      const titleEl = byId('paperDetailTitle');
      const pre = byId('paperDetailPre');
      if (titleEl) titleEl.textContent = paper.title || ('ID=' + id);
      if (pre) pre.textContent = JSON.stringify(paper, null, 2);
      if (mask) mask.style.display = 'flex';
    } catch (e) {
      showToast(e.message || '获取详情失败', 'error');
    }
  }

  function bindPaperDetailModal() {
    const mask = byId('paperDetailMask');
    const close = byId('paperDetailClose');
    if (close) {
      close.addEventListener('click', () => {
        if (mask) mask.style.display = 'none';
      });
    }
    if (mask) {
      mask.addEventListener('click', (e) => {
        if (e.target === mask) mask.style.display = 'none';
      });
    }
  }

  async function refresh() {
    const uname = curUname();
    const statsResp = await apiGet('/admin/stats?uname=' + encodeURIComponent(uname));
    setStats(statsResp.stats || {});

    const usersResp = await apiGet('/admin/users?uname=' + encodeURIComponent(uname));
    renderUsers(usersResp.users || []);
  }

  async function init() {
    const uname = curUname();
    if (!uname) return;

    try {
      const me = await apiGet('/admin/me?uname=' + encodeURIComponent(uname));
      if (!me.isAdmin) {
        showToast('你不是管理员，无权访问', 'error');
        setTimeout(() => (window.location.href = '/index.html'), 800);
        return;
      }
    } catch (e) {
      showToast(e.message || '管理员校验失败', 'error');
      setTimeout(() => (window.location.href = '/index.html'), 800);
      return;
    }

    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) refreshBtn.addEventListener('click', refresh);

    const previewBtn = byId('previewPapersBtn');
    if (previewBtn) previewBtn.addEventListener('click', () => previewPapers().catch(e => showToast(e.message || '预览失败', 'error')));

    const importBtn = byId('importPapersBtn');
    if (importBtn) importBtn.addEventListener('click', importPapers);

    const searchBtn = byId('papersSearchBtn');
    if (searchBtn) searchBtn.addEventListener('click', () => searchPapers(true));

    const qEl = byId('papersQuery');
    if (qEl) {
      qEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') searchPapers(true);
      });
    }

    const prevBtn = byId('papersPrevBtn');
    const nextBtn = byId('papersNextBtn');
    if (prevBtn) prevBtn.addEventListener('click', () => {
      const limit = parseInt(byId('papersLimit')?.value || '50', 10) || 50;
      papersOffset = Math.max(0, papersOffset - limit);
      searchPapers(false);
    });
    if (nextBtn) nextBtn.addEventListener('click', async () => {
      const limit = parseInt(byId('papersLimit')?.value || '50', 10) || 50;
      papersOffset = papersOffset + limit;
      await searchPapers(false);
    });

    const limitEl = byId('papersLimit');
    if (limitEl) limitEl.addEventListener('change', () => searchPapers(true));

    bindPaperDetailModal();

    await refresh();

    // 初次加载 papers 列表（空查询，默认最新）
    await searchPapers(true);
  }

  window.AdminPanel = { init };
})();
