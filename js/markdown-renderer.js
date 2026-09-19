/* Safe Markdown rendering for AI-generated chatbot answers. */
(function (global) {
  'use strict';

  function normalizeAnswer(value) {
    if (value == null) return '';
    if (typeof value === 'string') {
      var trimmed = value.trim();
      if ((trimmed.charAt(0) === '{' && trimmed.charAt(trimmed.length - 1) === '}')
        || (trimmed.charAt(0) === '[' && trimmed.charAt(trimmed.length - 1) === ']')) {
        try { return normalizeAnswer(JSON.parse(trimmed)); } catch (ignore) {}
      }
      return value;
    }
    if (value.content || value.message || value.response) {
      return normalizeAnswer(value.content || value.message || value.response);
    }
    return Object.keys(value).filter(function (key) {
      return value[key] !== null && value[key] !== undefined && value[key] !== ''
        && key !== 'status' && key !== 'query';
    }).map(function (key) {
      var label = key.replace(/_/g, ' ').replace(/\b\w/g, function (letter) { return letter.toUpperCase(); });
      var item = typeof value[key] === 'object' ? JSON.stringify(value[key]) : value[key];
      return '**' + label + ':** ' + item;
    }).join('\n');
  }

  function escapeHtml(value) {
    return String(value).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  function addTableClasses(cleanHtml) {
    var container = document.createElement('div');
    container.innerHTML = cleanHtml;
    container.querySelectorAll('table').forEach(function (table) {
      table.classList.add('chat-table');
      var wrapper = document.createElement('div');
      wrapper.className = 'chat-table-wrapper';
      table.parentNode.insertBefore(wrapper, table);
      wrapper.appendChild(table);
    });
    return container.innerHTML;
  }

  function render(value) {
    var text = normalizeAnswer(value);
    if (!text) return '';
    if (!global.marked || !global.DOMPurify) return escapeHtml(text).replace(/\r?\n/g, '<br>');

    var parsed = global.marked.parse(text, { gfm: true, breaks: true });
    var clean = global.DOMPurify.sanitize(parsed, {
      USE_PROFILES: { html: true },
      FORBID_TAGS: ['script', 'style', 'iframe', 'object', 'embed', 'form'],
      FORBID_ATTR: ['style', 'onerror', 'onload', 'onclick', 'onmouseover']
    });
    return addTableClasses(clean);
  }

  global.MarkdownRenderer = { render: render };
}(window));
