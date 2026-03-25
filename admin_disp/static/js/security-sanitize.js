(function () {
  'use strict';

  var inSanitizer = false;
  var INNER_PROP = 'inner' + 'HTML';
  var OUTER_PROP = 'outer' + 'HTML';
  var disableGlobalPatch = window.DISABLE_GLOBAL_SANITIZE_PATCH === true;

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function sanitizeHtml(value, contextElement) {
    var raw = String(value == null ? '' : value);

    // Evita recursividad cuando el sanitizer usa setters internos del DOM.
    if (inSanitizer) {
      return raw;
    }

    if (typeof window.DOMPurify !== 'undefined' && window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
      inSanitizer = true;
      try {
        // Preserve table fragments when assigning HTML to table sections.
        // Sanitizing raw <tr>/<td> without context can collapse structure.
        var tag = contextElement && contextElement.tagName ? String(contextElement.tagName).toLowerCase() : '';
        if (tag === 'tbody' || tag === 'thead' || tag === 'tfoot') {
          var wrappedSection = '<table><' + tag + '>' + raw + '</' + tag + '></table>';
          var cleanSection = window.DOMPurify.sanitize(wrappedSection, { USE_PROFILES: { html: true } });
          var sectionTpl = document.createElement('template');
          sectionTpl.innerHTML = cleanSection;
          var sectionNode = sectionTpl.content.querySelector(tag);
          return sectionNode ? sectionNode.innerHTML : '';
        }

        if (tag === 'tr') {
          var wrappedRow = '<table><tbody><tr>' + raw + '</tr></tbody></table>';
          var cleanRow = window.DOMPurify.sanitize(wrappedRow, { USE_PROFILES: { html: true } });
          var rowTpl = document.createElement('template');
          rowTpl.innerHTML = cleanRow;
          var rowNode = rowTpl.content.querySelector('tr');
          return rowNode ? rowNode.innerHTML : '';
        }

        return window.DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } });
      } finally {
        inSanitizer = false;
      }
    }

    return escapeHtml(raw);
  }

  window.safeSanitizeHtml = sanitizeHtml;
  window.safeSetHTML = function (element, html) {
    if (!element) {
      return;
    }
    var proto = window.Element && window.Element.prototype;
    var desc = proto ? Object.getOwnPropertyDescriptor(proto, INNER_PROP) : null;
    if (desc && typeof desc.set === 'function') {
      desc.set.call(element, sanitizeHtml(html, element));
    }
  };

  var elementProto = window.Element && window.Element.prototype;
  if (elementProto && !disableGlobalPatch) {
    var innerDesc = Object.getOwnPropertyDescriptor(elementProto, INNER_PROP);
    if (innerDesc && typeof innerDesc.set === 'function') {
      var rawInnerSet = innerDesc.set;
      Object.defineProperty(elementProto, INNER_PROP, {
        configurable: true,
        enumerable: innerDesc.enumerable,
        get: innerDesc.get,
        set: function (value) {
          rawInnerSet.call(this, sanitizeHtml(value, this));
        }
      });
    }

    var outerDesc = Object.getOwnPropertyDescriptor(elementProto, OUTER_PROP);
    if (outerDesc && typeof outerDesc.set === 'function') {
      var rawOuterSet = outerDesc.set;
      Object.defineProperty(elementProto, OUTER_PROP, {
        configurable: true,
        enumerable: outerDesc.enumerable,
        get: outerDesc.get,
        set: function (value) {
          rawOuterSet.call(this, sanitizeHtml(value, this));
        }
      });
    }
  }

  var docProto = window.Document && window.Document.prototype;
  if (docProto && !disableGlobalPatch) {
    if (typeof docProto.write === 'function') {
      var rawWrite = docProto.write;
      docProto.write = function () {
        var sanitized = [];
        for (var i = 0; i < arguments.length; i += 1) {
          sanitized.push(sanitizeHtml(arguments[i]));
        }
        return rawWrite.apply(this, sanitized);
      };
    }

    if (typeof docProto.writeln === 'function') {
      var rawWriteln = docProto.writeln;
      docProto.writeln = function () {
        var sanitized = [];
        for (var i = 0; i < arguments.length; i += 1) {
          sanitized.push(sanitizeHtml(arguments[i]));
        }
        return rawWriteln.apply(this, sanitized);
      };
    }
  }
})();
