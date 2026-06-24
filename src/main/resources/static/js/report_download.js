(function () {
  function getUsernameSafe() {
    try {
      const user = getCurrentUser && getCurrentUser();
      if (!user) return null;
      if (typeof user === 'string') return user;
      if (typeof user === 'object') {
        return user.uname || user.username || user.name || null;
      }
      return null;
    } catch (e) {
      return null;
    }
  }

  function fmtDate(iso) {
    if (!iso) return '';
    try {
      const d = new Date(iso);
      return d.toLocaleString('zh-CN', { hour12: false });
    } catch (e) {
      return String(iso);
    }
  }

  function buildOptionLabel(item) {
    const pieces = [];
    if (item.originalName) pieces.push(item.originalName);
    else if (item.filename) pieces.push(item.filename);

    const meta = [];
    if (item.createdAt) meta.push(fmtDate(item.createdAt));
    if (typeof item.totalPapers === 'number') meta.push(item.totalPapers + ' 篇');
    if (typeof item.journalCount === 'number') meta.push(item.journalCount + ' 期刊');
    if (meta.length) pieces.push('（' + meta.join(' / ') + '）');

    return pieces.join(' ');
  }

  async function fetchHistory(username) {
    const url = '/analysis/history?username=' + encodeURIComponent(username);
    const resp = await fetch(url);
    if (!resp.ok) {
      const text = await resp.text().catch(() => '');
      throw new Error('获取历史分析失败: ' + resp.status + ' ' + text);
    }
    const json = await resp.json();
    if (json && json.success === false) {
      throw new Error(json.message || '获取历史分析失败');
    }
    // ResponseUtils.success 会把 data merge 到最外层，所以直接读 history
    return (json && Array.isArray(json.history)) ? json.history : [];
  }

  function setVisible(id, visible) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = visible ? '' : 'none';
  }

  function setEmptyState(title, subtitle) {
    const root = document.getElementById('emptyState');
    if (!root) return;
    const h2 = root.querySelector('h2');
    const muted = root.querySelector('.muted');
    if (h2 && title) h2.textContent = title;
    if (muted && subtitle) muted.textContent = subtitle;
  }

  async function init() {
    const username = getUsernameSafe();
    if (!username) {
      setEmptyState('无法获取当前用户信息', '请重新登录后再尝试下载报告。');
      setVisible('emptyState', true);
      setVisible('pickerCard', false);
      return;
    }

    const emptyState = document.getElementById('emptyState');
    const pickerCard = document.getElementById('pickerCard');
    const analysisSelect = document.getElementById('analysisSelect');
    const downloadBtn = document.getElementById('downloadBtn');
    const pickerHint = document.getElementById('pickerHint');

    if (!emptyState || !pickerCard || !analysisSelect || !downloadBtn || !pickerHint) return;

    setVisible('emptyState', false);
    setVisible('pickerCard', false);

    let history;
    try {
      history = await fetchHistory(username);
    } catch (e) {
      console.error(e);
      // 请求失败：展示错误，不要自动跳转
      setEmptyState('获取分析记录失败', '网络异常或登录状态失效，请稍后刷新重试，或重新登录。');
      setVisible('emptyState', true);
      setVisible('pickerCard', false);
      return;
    }

    if (!Array.isArray(history) || history.length === 0) {
      setEmptyState('你还没有分析过数据', '快去分析吧～完成一次分析后，这里就可以选择并下载报告。');
      setVisible('emptyState', true);
      setVisible('pickerCard', false);
      return;
    }

    // Populate select
    analysisSelect.innerHTML = '';
    for (const item of history) {
      const opt = document.createElement('option');
      opt.value = String(item.id ?? '');
      opt.textContent = buildOptionLabel(item);
      analysisSelect.appendChild(opt);
    }

    pickerHint.textContent = '当前用户：' + username + '（最近 ' + history.length + ' 次分析）';
    setVisible('emptyState', false);
    setVisible('pickerCard', true);

    downloadBtn.addEventListener('click', () => {
      const analysisId = analysisSelect.value;
      if (!analysisId) {
        alert('请选择要下载的分析记录');
        return;
      }

      const url =
        '/report/download?username=' +
        encodeURIComponent(username) +
        '&analysisId=' +
        encodeURIComponent(analysisId);

      // 更稳健的下载：先请求，检测状态码，再触发浏览器保存
      downloadBtn.disabled = true;
      const original = downloadBtn.innerHTML;
      downloadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 打包中...';

      fetch(url)
        .then(async (resp) => {
          if (!resp.ok) {
            const text = await resp.text().catch(() => '');
            let msg = '下载失败：' + resp.status;
            if (resp.status === 403) msg = '下载失败：这条记录不属于当前用户';
            else if (resp.status === 404) msg = '下载失败：记录不存在';
            else if (text) msg += ' ' + text;
            throw new Error(msg);
          }
          const blob = await resp.blob();
          const downloadUrl = window.URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = downloadUrl;
          a.download = 'report_' + analysisId + '.zip';
          document.body.appendChild(a);
          a.click();
          a.remove();
          window.URL.revokeObjectURL(downloadUrl);
        })
        .catch((err) => {
          console.error(err);
          alert(err.message || '下载失败，请稍后重试');
        })
        .finally(() => {
          downloadBtn.disabled = false;
          downloadBtn.innerHTML = original;
        });
    });
  }

  window.ReportDownloadPage = { init };
})();
