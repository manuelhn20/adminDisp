(function () {
  'use strict';

  var inSanitizer = false;

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function sanitizeHtml(value) {
    var raw = String(value == null ? '' : value);

    // Evita recursividad cuando el sanitizer usa internamente innerHTML.
    if (inSanitizer) {
      return raw;
    }

    if (typeof window.DOMPurify !== 'undefined' && window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
      inSanitizer = true;
      try {
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
    element.innerHTML = sanitizeHtml(html);
  };

  var elementProto = window.Element && window.Element.prototype;
  if (elementProto) {
    var innerDesc = Object.getOwnPropertyDescriptor(elementProto, 'innerHTML');
    if (innerDesc && typeof innerDesc.set === 'function') {
      var rawInnerSet = innerDesc.set;
      Object.defineProperty(elementProto, 'innerHTML', {
        configurable: true,
        enumerable: innerDesc.enumerable,
        get: innerDesc.get,
        set: function (value) {
          rawInnerSet.call(this, sanitizeHtml(value));
        }
      });
    }

    var outerDesc = Object.getOwnPropertyDescriptor(elementProto, 'outerHTML');
    if (outerDesc && typeof outerDesc.set === 'function') {
      var rawOuterSet = outerDesc.set;
      Object.defineProperty(elementProto, 'outerHTML', {
        configurable: true,
        enumerable: outerDesc.enumerable,
        get: outerDesc.get,
        set: function (value) {
          rawOuterSet.call(this, sanitizeHtml(value));
        }
      });
    }
  }

  var docProto = window.Document && window.Document.prototype;
  if (docProto) {
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
