// Reusable dataset picker modal
// Usage:
//   const picker = window.DatasetPickerModal.getInstance();
//   picker.open({ items: [{id,title,meta,href}], selectedId, onSelect, options: { pageSize: 10 } })

(function () {
  const DEFAULTS = {
    title: '选择数据集',
    placeholder: '搜索文件名 / ID / 时间...',
    emptyText: '没有可选择的数据集',
    pageSize: 10,
  };

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  class DatasetPickerModal {
    constructor() {
      this._mounted = false;
      this._state = {
        items: [],
        selectedId: null,
        onSelect: null,
        options: { ...DEFAULTS },
        page: 1,
      };

      this._onKeyDown = (e) => {
        if (e.key === 'Escape') {
          this.close();
        }
      };
    }

    static getInstance() {
      if (!window.__pmDatasetPickerModal) {
        window.__pmDatasetPickerModal = new DatasetPickerModal();
      }
      return window.__pmDatasetPickerModal;
    }

    mount() {
      if (this._mounted) return;

      const backdrop = document.createElement('div');
      backdrop.className = 'pm-modal-backdrop';
      backdrop.style.display = 'none';
      backdrop.innerHTML = `
        <div class="pm-modal" role="dialog" aria-modal="true" aria-label="dataset picker">
          <div class="pm-modal-header">
            <div class="pm-modal-title" id="pmDatasetPickerTitle">选择数据集</div>
            <button type="button" class="pm-modal-close" aria-label="close">×</button>
          </div>
          <div class="pm-modal-body">
            <input type="text" class="pm-modal-search" id="pmDatasetPickerSearch" placeholder="搜索..." autocomplete="off" />
            <div class="pm-modal-list" id="pmDatasetPickerList"></div>
            <div class="pm-modal-empty" id="pmDatasetPickerEmpty" style="display:none;"></div>
            <div class="pm-modal-footer" id="pmDatasetPickerPager" style="display:none;">
              <button type="button" class="pm-modal-pager-btn" id="pmDatasetPickerPrev">上一页</button>
              <div class="pm-modal-pager-info" id="pmDatasetPickerPagerInfo"></div>
              <button type="button" class="pm-modal-pager-btn" id="pmDatasetPickerNext">下一页</button>
            </div>
          </div>
        </div>
      `;

      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) this.close();
      });

      const closeBtn = backdrop.querySelector('.pm-modal-close');
      closeBtn.addEventListener('click', () => this.close());

      const search = backdrop.querySelector('#pmDatasetPickerSearch');
      search.addEventListener('input', () => {
        this._state.page = 1;
        this._renderList();
      });

      document.body.appendChild(backdrop);

      this._elBackdrop = backdrop;
      this._elTitle = backdrop.querySelector('#pmDatasetPickerTitle');
      this._elSearch = search;
      this._elList = backdrop.querySelector('#pmDatasetPickerList');
      this._elEmpty = backdrop.querySelector('#pmDatasetPickerEmpty');
      this._elPager = backdrop.querySelector('#pmDatasetPickerPager');
      this._elPagerInfo = backdrop.querySelector('#pmDatasetPickerPagerInfo');
      this._elPagerPrev = backdrop.querySelector('#pmDatasetPickerPrev');
      this._elPagerNext = backdrop.querySelector('#pmDatasetPickerNext');

      if (this._elPagerPrev) {
        this._elPagerPrev.addEventListener('click', () => {
          if (this._state.page > 1) {
            this._state.page -= 1;
            this._renderList();
          }
        });
      }

      if (this._elPagerNext) {
        this._elPagerNext.addEventListener('click', () => {
          this._state.page += 1;
          this._renderList();
        });
      }

      this._mounted = true;
    }

    open({ items, selectedId, onSelect, options } = {}) {
      this.mount();

      this._state.items = Array.isArray(items) ? items : [];
      this._state.selectedId = selectedId ?? null;
      this._state.onSelect = typeof onSelect === 'function' ? onSelect : null;
      this._state.options = { ...DEFAULTS, ...(options || {}) };
      this._state.page = 1;

      this._elTitle.textContent = this._state.options.title;
      this._elSearch.value = '';
      this._elSearch.placeholder = this._state.options.placeholder;

      this._elBackdrop.style.display = 'flex';
      document.addEventListener('keydown', this._onKeyDown);

      this._renderList();
      setTimeout(() => this._elSearch.focus(), 0);
    }

    close() {
      if (!this._mounted) return;
      this._elBackdrop.style.display = 'none';
      document.removeEventListener('keydown', this._onKeyDown);
    }

    _renderList() {
      const q = (this._elSearch.value || '').trim().toLowerCase();
      const filtered = this._state.items.filter((it) => {
        if (!q) return true;
        const hay = `${it.title || ''} ${it.meta || ''} ${it.id || ''}`.toLowerCase();
        return hay.includes(q);
      });

      const pageSize = Math.max(1, parseInt(this._state.options.pageSize, 10) || 10);
      const total = filtered.length;
      const totalPages = Math.max(1, Math.ceil(total / pageSize));
      if (this._state.page < 1) this._state.page = 1;
      if (this._state.page > totalPages) this._state.page = totalPages;
      const start = (this._state.page - 1) * pageSize;
      const items = filtered.slice(start, start + pageSize);

      if (!filtered.length) {
        this._elList.innerHTML = '';
        this._elEmpty.style.display = 'block';
        this._elEmpty.textContent = this._state.options.emptyText;
        if (this._elPager) this._elPager.style.display = 'none';
        return;
      }

      this._elEmpty.style.display = 'none';

      if (this._elPager) {
        this._elPager.style.display = 'flex';
        this._elPagerPrev.disabled = this._state.page <= 1;
        this._elPagerNext.disabled = this._state.page >= totalPages;
        this._elPagerInfo.textContent = `第 ${this._state.page}/${totalPages} 页（共 ${total} 条）`;
      }

      this._elList.innerHTML = items
        .map((it) => {
          const isActive = this._state.selectedId != null && String(it.id) === String(this._state.selectedId);
          return `
            <button type="button" class="pm-modal-item${isActive ? ' active' : ''}" data-id="${escapeHtml(it.id)}">
              <div class="pm-modal-item-title">${escapeHtml(it.title || '')}</div>
              <div class="pm-modal-item-meta">${escapeHtml(it.meta || '')}</div>
            </button>
          `;
        })
        .join('');

      this._elList.scrollTop = 0;

      this._elList.querySelectorAll('.pm-modal-item').forEach((btn) => {
        btn.addEventListener('click', () => {
          const id = btn.getAttribute('data-id');
          const item = this._state.items.find((x) => String(x.id) === String(id));
          if (item && this._state.onSelect) {
            this._state.onSelect(item);
          }
          this.close();
        });
      });
    }
  }

  window.DatasetPickerModal = DatasetPickerModal;
})();
