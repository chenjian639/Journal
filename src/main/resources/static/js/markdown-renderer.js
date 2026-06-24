// Minimal, safe Markdown renderer for AI outputs.
// - Escapes HTML by default
// - Supports: headings, lists, blockquotes, code fences, inline code, bold/italic, links
// - Intended for rendering trusted markdown-like text from AI (still sanitized)

(function () {
  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function isSafeHref(href) {
    if (!href) return false;
    const h = String(href).trim();
    if (h.startsWith('/')) return true;
    if (/^https?:\/\//i.test(h)) return true;
    return false;
  }

  function renderInline(text) {
    if (text == null) return '';

    // Split by backticks to preserve code spans
    const parts = String(text).split('`');
    let out = '';
    for (let idx = 0; idx < parts.length; idx++) {
      const seg = parts[idx];
      if (idx % 2 === 1) {
        out += `<code>${escapeHtml(seg)}</code>`;
        continue;
      }

      // Extract links first (on raw segment), replace with tokens
      const links = [];
      let raw = seg;
      raw = raw.replace(/\[([^\]]+?)\]\(([^)]+?)\)/g, (_, t, u) => {
        const token = `@@PM_LINK_${links.length}@@`;
        links.push({ text: t, url: u });
        return token;
      });

      // Escape the rest
      let escaped = escapeHtml(raw);

      // Bold then italic (conservative)
      escaped = escaped.replace(/\*\*([^*]+?)\*\*/g, '<strong>$1</strong>');
      escaped = escaped.replace(/\*([^*]+?)\*/g, '<em>$1</em>');

      // Put links back
      for (let i = 0; i < links.length; i++) {
        const token = `@@PM_LINK_${i}@@`;
        const link = links[i];
        const safe = isSafeHref(link.url);
        const textHtml = escapeHtml(link.text);
        if (safe) {
          const href = escapeHtml(String(link.url).trim());
          escaped = escaped.replace(
            token,
            `<a href="${href}" target="_blank" rel="noopener noreferrer">${textHtml}</a>`
          );
        } else {
          escaped = escaped.replace(token, textHtml);
        }
      }

      out += escaped;
    }

    return out;
  }

  function render(md) {
    if (md == null) return '';
    const text = String(md).replace(/\r\n/g, '\n');
    const lines = text.split('\n');

    let html = '';
    let i = 0;

    function isBlockStart(line) {
      return (
        /^```/.test(line) ||
        /^#{1,6}\s+/.test(line) ||
        /^>\s?/.test(line) ||
        /^\s*[-*]\s+/.test(line) ||
        /^\s*\d+\.\s+/.test(line)
      );
    }

    while (i < lines.length) {
      const line = lines[i];

      // Skip empty lines
      if (!line || line.trim() === '') {
        i++;
        continue;
      }

      // Code fence
      if (/^```/.test(line)) {
        const lang = (line.match(/^```\s*([\w-]+)?/) || [])[1] || '';
        i++;
        const codeLines = [];
        while (i < lines.length && !/^```/.test(lines[i])) {
          codeLines.push(lines[i]);
          i++;
        }
        if (i < lines.length && /^```/.test(lines[i])) i++;
        const code = codeLines.join('\n');
        html += `<pre><code${lang ? ` class="language-${escapeHtml(lang)}"` : ''}>${escapeHtml(code)}</code></pre>`;
        continue;
      }

      // Heading
      const h = line.match(/^(#{1,6})\s+(.+)$/);
      if (h) {
        const level = h[1].length;
        html += `<h${level}>${renderInline(h[2].trim())}</h${level}>`;
        i++;
        continue;
      }

      // Blockquote
      if (/^>\s?/.test(line)) {
        const qLines = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) {
          qLines.push(lines[i].replace(/^>\s?/, ''));
          i++;
        }
        const inner = qLines
          .map((l) => (l.trim() === '' ? '' : renderInline(l)))
          .join('<br>');
        html += `<blockquote>${inner}</blockquote>`;
        continue;
      }

      // Unordered list
      if (/^\s*[-*]\s+/.test(line)) {
        const items = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*[-*]\s+/, ''));
          i++;
        }
        html += `<ul>${items.map((it) => `<li>${renderInline(it)}</li>`).join('')}</ul>`;
        continue;
      }

      // Ordered list
      if (/^\s*\d+\.\s+/.test(line)) {
        const items = [];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
          items.push(lines[i].replace(/^\s*\d+\.\s+/, ''));
          i++;
        }
        html += `<ol>${items.map((it) => `<li>${renderInline(it)}</li>`).join('')}</ol>`;
        continue;
      }

      // Paragraph: collect until blank line or next block start
      const pLines = [];
      while (i < lines.length && lines[i].trim() !== '' && !isBlockStart(lines[i])) {
        pLines.push(lines[i]);
        i++;
      }
      const p = pLines.map((l) => renderInline(l)).join('<br>');
      html += `<p>${p}</p>`;
    }

    return html;
  }

  window.PaperMasterMarkdown = {
    render,
    renderInline,
    escapeHtml,
  };
})();
