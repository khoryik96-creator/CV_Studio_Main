// ── Hyppies Logo & Export Helpers ────────────────────────────────────
var HYPPIES_LOGO_URI = 'data:image/jpeg;base64,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eQq8cvQ1wprEwjeTmRT9PP/EACkQAQABAwMCBAcBAAAAAAAAAAERACExQVFhcYFAkbHBECAwcKHR8FD/2gAIAQEAAT8h+3ErkKoS+Vcmtza3NrGtLAKXqA8NA9NeCfQZ7R8iSd5Vu/pW7vC5iXBl/Sv2fJvdnwL73q+FSaL66llngSO3xnzwWQmviIH5I+EmCkXXjd8HrSudllPjIwKbjoOuvFAGNAIA8GjAwkGXigrnSTRF6/gvev4L3qU47NE4JTUKQ7vULn/KMwu4qd7hVs32ByUF9xHUi8HczQy48wsSwWL60kRiMEDE3LLOYoKqIAh4RDVueW+UCoNYXavb6qc5nWCbNtd6yt5Ogi68u2aIuOAvRAntQVTVHoC9Y7VreoNz6p9A5ua/iSoI/lOnGm8VeWQzOF8r0nzRhqL3j0ipZFIHZ09iduQLC7sX3p+pwUguxQ9Co0kM9W+1S+EH6oO0qJ2I5va7oDvUM80VGzEawzxToKINi9QnRNyrNbXC4Tgviye/1TsU+pn5SgA7MJAfanEhjBeqBu5pQUwLrq6lSHAVklCahM4wkB1tPWa2uokgKOGOU8yR+Yq8hqLqlY1ZpgwV8IBttaeKdQS6kdkPN2o1OR/6OiVorNNW9gMH1yjRhaPcVZUACAq20NoznAw33+DvWVjs3x9vP//aAAwDAQACAAMAAAAQ88888888888888888888888888888888888888888888ww88888888888e+U8888888888G8O8888888888uc888888888qyqWcK28888888UMUOec8888888888888888888888888888888888888888888888888888888//EABQRAQAAAAAAAAAAAAAAAAAAAHD/2gAIAQMBAT8QKf/EACgRAQACAgAGAQIHAAAAAAAAAAERIQAxMEFRYYHRoRBQIHGRscHw8f/aAAgBAgEBPxD7XvP9t6waAPzeuJIlyHxp8nzP0qzmH8nh+I4bJbVO58SUdc/pPeIWLqRE+XfrhiQwop94kQB4feI3lbeCO4aWZbdCL1eM1Qh7QrJXy55sF1iKuCavlR6zp6AI0Tf7YlFk+tANd3uwYxdQNSMmiFE98NQQrcT+pSdz8azNgDwyZMBL0Ula5yzGNeE3INy2LMVg/thUG1kSZvJFaLLnLues4sZhAkQiHYkQzkpb1qADQBo+8f/EACUQAQEAAgICAQMFAQAAAAAAAAERITEAQVFhEDBAcSBQcIGRsf/aAAgBAQABPxD+ONh+lkFYBVxoK8SZb55cuRiTZGgtHxftt+3ggNh40jpeX6HYHURip+dztT7XPAIFGYvyMO0P0YbGURLJ+JL0fawBEEcI98URm2LL/gSA6D5MmQwA0Sg8qo95xiBYAV2wCuvtHRXhK9L2mO0GrGIgVp6Lo9GD5CZdFDcjzFjVaU4c+xAIgAaA6+zSS5MFDAVCusocWCkTnX8Tavar38v36B0PfRUl6YezjZKASnfNp/wAMB+1MLMiWzGqyDrYccnalSLAiYU/vg52QBxQCTqDPg51WbOgIKVBAd8RT15QmiUyShdZ5nvxEqAEy6jnrn9cvwsZpsywzxYRjU2p6HvDiUk6VOBFRg4xjmSFNhGYPc1aZvjpxiq+Mx9U8ZLDBG2hUFKhC8VmgMUupikZQsfq5NorkaAXJ0d8TTblwiMkwlvrjtwsMiVPH/NzugUCpIdkU8JynUYA6cdDMXy3h9G3bEs2s3NEzzL6FhQMO4Ve4vKnQRnLk+FD6Scv3f1ZNj0gPAB1yVJFmdrqoDsuS8VUu+QYDIkCyPs8LbVUWTPYIiMgkus8+HwQBVoZhPqnt6OuzjGFDvQ8oS5vK9gumckgoHnoyZgV8cnlZu45fgCckXlAaUB3LZxsmx12UceCp8PLQf1XuTt7V25eTS8FYOFkAQnRrrh/NdxlPGUrU6IAcT1wVQo0KkjIoEdjo3fXQXoKdRYlvCyuigAFGzAUUQYNUXuCeWF0ViAADhuPrPccx7EcoyBhxjgh19vC+1cq5XfLlWnGiLJDLB+GDJBnWVZdGGn8ef/Z';

function _escDoc(s) { return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function cvPdfSafeText(s) {
  // Offline PDF fallback uses a simple PDF text encoder; keep exported text safe
  // and readable by converting Word/LinkedIn smart punctuation before rendering.
  s = String(s || '');
  var map = {
    '\u00a0':' ', '\u00a9':'(c)', '\u00ae':'(R)', '\u2122':'(TM)', '\u2026':'...',
    '\u2013':'-', '\u2014':'-', '\u2212':'-', '\u2010':'-', '\u2011':'-',
    '\u2018':"'", '\u2019':"'", '\u201a':"'", '\u201b':"'",
    '\u201c':'"', '\u201d':'"', '\u201e':'"', '\u2033':'"', '\u2032':"'",
    '\u2022':'-', '\u25cf':'-', '\u25aa':'-', '\u2713':'✓', '\u2714':'✓'
  };
  s = s.replace(/[\u00a0\u00a9\u00ae\u2122\u2026\u2010\u2011\u2013\u2014\u2212\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u2032\u2033\u2022\u25cf\u25aa\u2713\u2714]/g, function(ch){ return map[ch] || ''; });
  try { s = s.normalize('NFKD').replace(/[\u0300-\u036f]/g, ''); } catch(e) {}
  s = s.replace(/\u2713/g, 'check');
  return s.replace(/[^\x09\x0A\x0D\x20-\x7E]/g, '');
}

function _wordDocShell(title, subtitle, bodyHtml) {
  return '<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">'
    + '<head><meta charset="UTF-8"><title>' + _escDoc(title||'Hyppies') + '</title>'
    + '<style>'
    + 'body{font-family:Calibri,Arial,sans-serif;font-size:11.5pt;color:#171717;line-height:1.55;margin:0;background:#fff;}'
    + '.page{max-width:760px;margin:0 auto;padding:34px 44px 28px;}'
    + '.brand{text-align:center;margin:0 0 22px;}'
    + '.hero{border:1px solid #e6e8ef;border-radius:12px;background:#fbfbfd;padding:22px 26px;margin:0 0 24px;}'
    + '.hero h1{font-size:21pt;line-height:1.22;margin:0 0 8px;color:#352a86;font-weight:700;}'
    + '.subtitle{font-size:10pt;color:#6b7280;margin:0;line-height:1.5;}'
    + 'h2{font-size:11pt;line-height:1.3;text-transform:uppercase;letter-spacing:.06em;margin:24px 0 10px;color:#352a86;border-bottom:1px solid #e5e7eb;padding-bottom:6px;}'
    + 'p{margin:7px 0 10px;line-height:1.62;} ul{margin:7px 0 14px 22px;padding:0;} li{margin:6px 0 7px;line-height:1.58;padding-left:2px;}'
    + '.chip{display:inline-block;border:1px solid #ddd6fe;background:#f5f3ff;color:#352a86;border-radius:14px;padding:3px 9px;margin:3px 5px 3px 0;font-size:9.5pt;font-weight:600;}'
    + '.callout{background:#f4fbf7;border:1px solid #c9eed8;border-radius:10px;padding:14px 18px;margin:20px 0 16px;}'
    + '.muted{color:#6b7280;}'
    + '.footer{margin-top:30px;border-top:1px solid #e5e7eb;padding-top:12px;color:#9ca3af;font-size:8.5pt;text-align:center;}'
    + '</style></head><body><div class="page">'
    + '<div class="brand"><img src="' + HYPPIES_LOGO_URI + '" alt="Hyppies" style="width:96px;height:auto;display:block;margin:0 auto;border:0"></div>'
    + '<div class="hero"><h1>' + _escDoc(title||'Hyppies') + '</h1>'
    + (subtitle ? '<p class="subtitle">' + _escDoc(subtitle) + '</p>' : '<p class="subtitle">Hyppies</p>')
    + '</div>' + bodyHtml
    + '<div class="footer">© Hyppies · Confidential · For candidate use only</div>'
    + '</div></body></html>';
}

function _safeFileStem(s) {
  return String(s||'export').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'') || 'export';
}
