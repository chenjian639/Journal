// 关键词分析页面逻辑

let currentPage = 1;
const pageSize = 20;
let currentKeyword = '';
let statusPollTimer = null;

let currentScope = 'global'; // 'global' | 'dataset'
let selectedDataset = null; // { username, filename, title, meta }

function $(id) {
    return document.getElementById(id);
}

function getUsername() {
    const user = getCurrentUser();
    return user ? user.uname : null;
}

function safeText(v) {
    return v === null || v === undefined ? '' : String(v);
}

function escapeHtml(str) {
    return safeText(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function formatDate(d) {
    const s = safeText(d).trim();
    return s || '-';
}

function buildJournalLink(journal) {
    const j = safeText(journal).trim();
    if (!j) return '-';
    return `<a href="/journal/${encodeURIComponent(j)}" target="_blank" rel="noopener">${escapeHtml(j)}</a>`;
}

async function apiGet(url) {
    const resp = await fetch(url, { method: 'GET', headers: { 'Accept': 'application/json' } });
    const data = await resp.json().catch(() => null);
    if (!resp.ok) {
        const msg = data && data.message ? data.message : `HTTP ${resp.status}`;
        throw new Error(msg);
    }
    // ResponseUtils.success: {success:true,message,data}
    return data && data.data ? data.data : data;
}

async function apiPostForm(url, formObj) {
    const body = new URLSearchParams();
    Object.keys(formObj || {}).forEach(k => body.append(k, String(formObj[k])));

    const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json' },
        body
    });

    const data = await resp.json().catch(() => null);
    if (!resp.ok) {
        const msg = data && data.message ? data.message : `HTTP ${resp.status}`;
        throw new Error(msg);
    }
    return data && data.data ? data.data : data;
}

function renderStatus(status) {
    const built = !!status.built;
    const building = !!status.building;
    const occ = status.occurrenceRows || 0;

    const scope = status.scope || (currentScope === 'dataset' ? 'dataset' : 'global');

    let text = '';
    if (built) {
        text = scope === 'dataset'
            ? `已就绪（user_keyword_occurrence: ${occ}）`
            : `已就绪（keyword_occurrence: ${occ}）`;
    } else {
        text = '未初始化（需要构建关键词索引）';
    }

    if (building) {
        text = '正在构建索引…';
    }

    $('indexStatusText').textContent = text;

    const total = Number(status.totalPapers || 0);
    const processed = Number(status.processedPapers || 0);

    const showProgress = building && total > 0;
    $('progressRow').style.display = showProgress ? '' : 'none';

    if (showProgress) {
        const pct = Math.max(0, Math.min(100, Math.floor((processed / total) * 100)));
        $('progressBar').style.width = pct + '%';
        $('progressText').textContent = `${processed}/${total}（${pct}%）`;
    }

    if (status.lastError) {
        showToast('索引构建失败：' + status.lastError, 'error');
    }
}

function stopStatusPolling() {
    if (statusPollTimer) {
        clearInterval(statusPollTimer);
        statusPollTimer = null;
    }
}

function startStatusPolling() {
    stopStatusPolling();
    statusPollTimer = setInterval(async () => {
        try {
            const data = await apiGet(buildKeywordApiUrl('/keyword/status'));
            renderStatus(data.status);
            if (!data.status.building) {
                stopStatusPolling();
                await loadTopKeywords();
            }
        } catch (e) {
            // ignore intermittent
        }
    }, 1500);
}

function renderTopKeywords(rows) {
    const box = $('topKeywords');
    if (!rows || rows.length === 0) {
        box.innerHTML = '<div class="empty-state">暂无数据（请先初始化索引）。</div>';
        return;
    }

    box.innerHTML = rows.map(r => {
        const kw = safeText(r.keyword);
        const cnt = Number(r.cnt || 0);
        return `<button class="kw-chip" data-kw="${escapeHtml(kw)}" title="出现次数：${cnt}">${escapeHtml(kw)} <span class="kw-chip-count">${cnt}</span></button>`;
    }).join('');

    box.querySelectorAll('.kw-chip').forEach(btn => {
        btn.addEventListener('click', () => {
            const kw = btn.getAttribute('data-kw') || '';
            $('keywordInput').value = kw;
            currentPage = 1;
            analyzeKeyword();
        });
    });
}

async function loadTopKeywords() {
    try {
        const data = await apiGet(buildKeywordApiUrl('/keyword/top?limit=30'));
        renderTopKeywords(data.rows);
    } catch (e) {
        $('topKeywords').innerHTML = '<div class="empty-state">加载失败</div>';
    }
}

function renderSummary(analysis) {
    const box = $('summaryBox');
    if (!analysis) {
        box.innerHTML = '<div class="empty-state">暂无数据</div>';
        return;
    }

    const earliest = analysis.earliest;
    const topJournal = analysis.topJournal;

    const earliestHtml = earliest
        ? `最早出现：${escapeHtml(formatDate(earliest.publishDate))} / ${buildJournalLink(earliest.journal)}`
        : '最早出现：-';

    const topJournalHtml = topJournal && topJournal.journal
        ? `最高频期刊：${buildJournalLink(topJournal.journal)}（${escapeHtml(safeText(topJournal.cnt))}）`
        : '最高频期刊：-';

    box.innerHTML = `
        <div class="kv-grid">
            <div class="kv-item"><div class="kv-k">关键词</div><div class="kv-v">${escapeHtml(analysis.keyword || '')}</div></div>
            <div class="kv-item"><div class="kv-k">命中论文数</div><div class="kv-v">${escapeHtml(safeText(analysis.totalPapers))}</div></div>
            <div class="kv-item"><div class="kv-k">命中期刊数</div><div class="kv-v">${escapeHtml(safeText(analysis.totalJournals))}</div></div>
        </div>
        <div class="summary-lines">
            <div class="summary-line">${earliestHtml}</div>
            <div class="summary-line">${topJournalHtml}</div>
        </div>
    `;
}

function renderJournalDist(journals) {
    const box = $('journalDist');
    if (!journals || journals.length === 0) {
        box.innerHTML = '<div class="empty-state">暂无数据</div>';
        return;
    }

    const max = Math.max(...journals.map(j => Number(j.cnt || 0)), 1);
    box.innerHTML = journals.map(j => {
        const name = safeText(j.journal);
        const cnt = Number(j.cnt || 0);
        const pct = Math.max(2, Math.floor((cnt / max) * 100));
        return `
            <div class="dist-row">
                <div class="dist-name">${buildJournalLink(name)}</div>
                <div class="dist-bar"><div class="dist-bar-inner" style="width:${pct}%"></div></div>
                <div class="dist-cnt">${cnt}</div>
            </div>
        `;
    }).join('');
}

function renderPapers(papers) {
    const tbody = $('papersTbody');
    if (!papers || papers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty-td">暂无数据</td></tr>';
        return;
    }

    tbody.innerHTML = papers.map(p => {
        const id = safeText(p.paperId);
        const title = safeText(p.title);
        const journal = safeText(p.journal);
        const publishDate = formatDate(p.publishDate);
        const doi = safeText(p.doi);
        const doiHtml = doi ? `<a href="https://doi.org/${encodeURIComponent(doi)}" target="_blank" rel="noopener">${escapeHtml(doi)}</a>` : '-';

        return `
            <tr>
                <td>${escapeHtml(id)}</td>
                <td class="td-title">${escapeHtml(title)}</td>
                <td>${buildJournalLink(journal)}</td>
                <td>${escapeHtml(publishDate)}</td>
                <td>${doiHtml}</td>
            </tr>
        `;
    }).join('');
}

async function analyzeKeyword() {
    const kw = $('keywordInput').value.trim();
    if (!kw) {
        showToast('请输入关键词', 'error');
        return;
    }

    if (currentScope === 'dataset' && !selectedDataset) {
        showToast('请先选择一个数据集', 'error');
        return;
    }

    currentKeyword = kw;

    $('analyzeBtn').disabled = true;
    $('summaryBox').innerHTML = '<div class="empty-state">加载中...</div>';

    try {
        const base = `/keyword/analyze?keyword=${encodeURIComponent(kw)}&page=${currentPage}&size=${pageSize}`;
        const url = buildKeywordApiUrl(base);
        const data = await apiGet(url);
        const analysis = data.analysis;
        renderSummary(analysis);
        renderJournalDist(analysis.journals || []);
        renderPapers(analysis.papers || []);
        $('pageText').textContent = `第 ${analysis.page || currentPage} 页`;

        const total = Number(analysis.totalPapers || 0);
        $('prevPage').disabled = currentPage <= 1;
        $('nextPage').disabled = currentPage * pageSize >= total;

    } catch (e) {
        const msg = safeText(e && e.message ? e.message : e);
        if (msg.includes('keyword index not built')) {
            showToast('关键词索引尚未构建，请先点击“初始化索引”。', 'error');
        } else {
            showToast('分析失败：' + msg, 'error');
        }
        renderSummary(null);
        renderJournalDist([]);
        renderPapers([]);
    } finally {
        $('analyzeBtn').disabled = false;
    }
}

async function initStatus() {
    try {
        const data = await apiGet(buildKeywordApiUrl('/keyword/status'));
        renderStatus(data.status);
    } catch (e) {
        $('indexStatusText').textContent = '加载失败';
    }
}

function setScope(scope) {
    currentScope = scope === 'dataset' ? 'dataset' : 'global';

    const globalBtn = $('scopeGlobalBtn');
    const datasetBtn = $('scopeDatasetBtn');
    const pickBtn = $('pickDatasetBtn');
    const hint = $('datasetHint');

    if (currentScope === 'global') {
        if (globalBtn) {
            globalBtn.classList.add('btn-primary');
            globalBtn.classList.remove('btn-outline');
        }
        if (datasetBtn) {
            datasetBtn.classList.add('btn-outline');
            datasetBtn.classList.remove('btn-primary');
        }
        if (pickBtn) pickBtn.style.display = 'none';
        if (hint) {
            hint.style.display = 'none';
            hint.textContent = '';
        }
    } else {
        if (datasetBtn) {
            datasetBtn.classList.add('btn-primary');
            datasetBtn.classList.remove('btn-outline');
        }
        if (globalBtn) {
            globalBtn.classList.add('btn-outline');
            globalBtn.classList.remove('btn-primary');
        }
        if (pickBtn) pickBtn.style.display = '';
        updateDatasetHint();
    }
}

function updateDatasetHint() {
    const hint = $('datasetHint');
    if (!hint) return;

    if (currentScope !== 'dataset') {
        hint.style.display = 'none';
        hint.textContent = '';
        return;
    }

    hint.style.display = '';
    if (!selectedDataset) {
        hint.textContent = '未选择数据集';
        return;
    }

    const title = selectedDataset.title || selectedDataset.filename;
    hint.textContent = `当前：${title}`;
}

function buildKeywordApiUrl(baseUrl) {
    if (currentScope !== 'dataset') return baseUrl;
    if (!selectedDataset) return baseUrl;

    const joiner = baseUrl.includes('?') ? '&' : '?';
    return `${baseUrl}${joiner}username=${encodeURIComponent(selectedDataset.username)}&filename=${encodeURIComponent(selectedDataset.filename)}`;
}

async function fetchDatasetItems(username) {
    const data = await apiGet(`/analysis/history?username=${encodeURIComponent(username)}`);
    const history = (data && data.history) ? data.history : [];
    return history.map((it) => {
        const title = it.originalName || it.filename || '未命名数据集';
        const createdAt = it.createdAt ? String(it.createdAt) : '';
        const meta = `ID: ${it.filename || ''}${createdAt ? ' · ' + createdAt : ''}`;
        return {
            id: it.filename,
            title,
            meta,
            raw: it
        };
    });
}

async function openDatasetPicker() {
    const username = getUsername();
    if (!username) {
        showToast('请先登录再选择数据集', 'error');
        window.location.href = '/auth/login.html?redirect=' + encodeURIComponent('/keyword_analysis.html');
        return;
    }

    try {
        const items = await fetchDatasetItems(username);
        const picker = window.DatasetPickerModal && window.DatasetPickerModal.getInstance
            ? window.DatasetPickerModal.getInstance()
            : null;

        if (!picker) {
            showToast('数据集选择器未加载', 'error');
            return;
        }

        picker.open({
            items,
            selectedId: selectedDataset ? selectedDataset.filename : null,
            options: {
                title: '选择用户上传数据集',
                placeholder: '搜索文件名 / ID / 时间...',
                emptyText: '暂无可用数据集（请先去“期刊分析”上传并完成分析）',
                pageSize: 10,
            },
            onSelect: async (item) => {
                selectedDataset = {
                    username,
                    filename: item.id,
                    title: item.title,
                    meta: item.meta,
                };
                setScope('dataset');
                currentPage = 1;
                await initStatus();
                await loadTopKeywords();

                // 若该数据集尚未构建索引，则自动启动构建
                try {
                    const st = await apiGet(buildKeywordApiUrl('/keyword/status'));
                    if (st && st.status && !st.status.built) {
                        await apiPostForm('/keyword/build-index', {
                            force: 'false',
                            username: selectedDataset.username,
                            filename: selectedDataset.filename,
                        });
                        showToast('已开始为数据集构建关键词索引', 'success');
                        startStatusPolling();
                    }
                } catch (e) {
                    // ignore
                }
            }
        });
    } catch (e) {
        showToast('加载数据集失败：' + safeText(e && e.message ? e.message : e), 'error');
    }
}

function bindEvents() {
    $('analyzeBtn').addEventListener('click', () => {
        currentPage = 1;
        analyzeKeyword();
    });

    $('keywordInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            currentPage = 1;
            analyzeKeyword();
        }
    });

    $('buildIndexBtn').addEventListener('click', async () => {
        try {
            $('buildIndexBtn').disabled = true;
            if (currentScope === 'dataset') {
                if (!selectedDataset) {
                    showToast('请先选择数据集', 'error');
                    return;
                }
                await apiPostForm('/keyword/build-index', {
                    force: 'false',
                    username: selectedDataset.username,
                    filename: selectedDataset.filename,
                });
            } else {
                await apiPostForm('/keyword/build-index', { force: 'false' });
            }
            showToast('已开始构建索引（后台执行）', 'success');
            startStatusPolling();
        } catch (e) {
            showToast('启动构建失败：' + safeText(e && e.message ? e.message : e), 'error');
        } finally {
            $('buildIndexBtn').disabled = false;
        }
    });

    const globalBtn = $('scopeGlobalBtn');
    if (globalBtn) {
        globalBtn.addEventListener('click', async () => {
            setScope('global');
            currentPage = 1;
            await initStatus();
            await loadTopKeywords();
        });
    }

    const datasetBtn = $('scopeDatasetBtn');
    if (datasetBtn) {
        datasetBtn.addEventListener('click', async () => {
            setScope('dataset');
            if (!selectedDataset) {
                await openDatasetPicker();
            } else {
                currentPage = 1;
                await initStatus();
                await loadTopKeywords();
            }
        });
    }

    const pickBtn = $('pickDatasetBtn');
    if (pickBtn) {
        pickBtn.addEventListener('click', openDatasetPicker);
    }

    $('prevPage').addEventListener('click', () => {
        if (currentPage <= 1) return;
        currentPage -= 1;
        analyzeKeyword();
    });

    $('nextPage').addEventListener('click', () => {
        currentPage += 1;
        analyzeKeyword();
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    bindEvents();
    setScope('global');
    await initStatus();
    await loadTopKeywords();
});
