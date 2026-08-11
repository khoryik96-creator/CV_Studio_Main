// Real .docx export, built entirely in the browser (this is an offline app, so
// no server round-trip and no new route). Converts the same export HTML the
// Word exports already produce (Blind JD / Company Profile / CV Scoring / The
// Owl) into a genuine OOXML .docx package — a proper, warning-free, editable
// Word document. Chosen by the Settings "Word export format" toggle; the legacy
// HTML-as-.doc export stays available for its richer CSS rendering.
//
// Scope: the HTML subset those exports use — h1..h4, p (with <br>), ul/ol/li,
// tables, and inline strong/b, em/i, span. Layout wrappers (div, hero, footer,
// chips, callouts) are flattened to clean structure; the logo image is omitted.

// ── minimal store-method ZIP writer (a .docx is a ZIP) ──────────────────────
function _docxCrc32(bytes) {
  var crc = ~0;
  for (var i = 0; i < bytes.length; i++) {
    crc ^= bytes[i];
    for (var j = 0; j < 8; j++) crc = (crc >>> 1) ^ (0xEDB88320 & -(crc & 1));
  }
  return (~crc) >>> 0;
}

function _docxZip(files) {
  var enc = new TextEncoder();
  var chunks = [], central = [], offset = 0, i;
  function u8(len) { return new Uint8Array(len); }
  for (i = 0; i < files.length; i++) {
    var name = enc.encode(files[i].name);
    var data = files[i].data;
    var crc = _docxCrc32(data), size = data.length;
    var lh = new DataView(new ArrayBuffer(30));
    lh.setUint32(0, 0x04034b50, true);
    lh.setUint16(4, 20, true); lh.setUint16(6, 0x0800, true); // UTF-8 flag
    lh.setUint16(8, 0, true); // store
    lh.setUint16(10, 0, true); lh.setUint16(12, 0x0021, true); // time/date
    lh.setUint32(14, crc, true); lh.setUint32(18, size, true); lh.setUint32(22, size, true);
    lh.setUint16(26, name.length, true); lh.setUint16(28, 0, true);
    chunks.push(new Uint8Array(lh.buffer), name, data);
    var cd = new DataView(new ArrayBuffer(46));
    cd.setUint32(0, 0x02014b50, true);
    cd.setUint16(4, 20, true); cd.setUint16(6, 20, true); cd.setUint16(8, 0x0800, true);
    cd.setUint16(10, 0, true); cd.setUint16(12, 0, true); cd.setUint16(14, 0x0021, true);
    cd.setUint32(16, crc, true); cd.setUint32(20, size, true); cd.setUint32(24, size, true);
    cd.setUint16(28, name.length, true);
    cd.setUint32(42, offset, true);
    central.push({ header: new Uint8Array(cd.buffer), name: name });
    offset += 30 + name.length + size;
  }
  var centralStart = offset, centralSize = 0;
  for (i = 0; i < central.length; i++) {
    chunks.push(central[i].header, central[i].name);
    centralSize += 46 + central[i].name.length;
  }
  var eo = new DataView(new ArrayBuffer(22));
  eo.setUint32(0, 0x06054b50, true);
  eo.setUint16(8, files.length, true); eo.setUint16(10, files.length, true);
  eo.setUint32(12, centralSize, true); eo.setUint32(16, centralStart, true);
  chunks.push(new Uint8Array(eo.buffer));
  var total = 0; for (i = 0; i < chunks.length; i++) total += chunks[i].length;
  var out = u8(total), p = 0;
  for (i = 0; i < chunks.length; i++) { out.set(chunks[i], p); p += chunks[i].length; }
  return out;
}

// ── HTML → OOXML ────────────────────────────────────────────────────────────
function _docxEsc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

var _DOCX_HEADINGS = { H1: 1, H2: 2, H3: 3, H4: 4 };

function _docxInlineRuns(node, bold, italic, out) {
  for (var i = 0; i < node.childNodes.length; i++) {
    var child = node.childNodes[i];
    if (child.nodeType === 3) { // text
      var text = child.nodeValue.replace(/\s+/g, ' ');
      if (text) out.push({ text: text, bold: bold, italic: italic });
    } else if (child.nodeType === 1) {
      var t = child.tagName;
      if (t === 'BR') { out.push({ text: '\n', bold: false, italic: false }); }
      else if (t === 'IMG') { /* skip images */ }
      else if (t === 'STRONG' || t === 'B') _docxInlineRuns(child, true, italic, out);
      else if (t === 'EM' || t === 'I') _docxInlineRuns(child, bold, true, out);
      else _docxInlineRuns(child, bold, italic, out); // span and others: inline
    }
  }
  return out;
}

function _docxTrimRuns(runs) {
  while (runs.length && runs[0].text.trim() === '' && runs[0].text !== '\n') runs.shift();
  while (runs.length && runs[runs.length - 1].text.trim() === '' && runs[runs.length - 1].text !== '\n') runs.pop();
  return runs;
}

function _docxWalk(node, blocks, listDepth, ordered) {
  for (var i = 0; i < node.childNodes.length; i++) {
    var el = node.childNodes[i];
    if (el.nodeType !== 1) continue;
    var tag = el.tagName;
    if (_DOCX_HEADINGS[tag]) {
      var hr = _docxTrimRuns(_docxInlineRuns(el, false, false, []));
      if (hr.length) blocks.push({ type: 'heading', level: _DOCX_HEADINGS[tag], runs: hr });
    } else if (tag === 'P') {
      var pr = _docxTrimRuns(_docxInlineRuns(el, false, false, []));
      if (pr.length) blocks.push({ type: 'paragraph', runs: pr });
    } else if (tag === 'UL' || tag === 'OL') {
      _docxWalk(el, blocks, listDepth + 1, tag === 'OL');
    } else if (tag === 'LI') {
      var lr = _docxTrimRuns(_docxInlineRuns(el, false, false, []));
      if (lr.length) blocks.push({ type: 'listitem', ordered: ordered, level: Math.max(0, listDepth - 1), runs: lr });
      // nested lists inside the <li>
      for (var k = 0; k < el.childNodes.length; k++) {
        var c = el.childNodes[k];
        if (c.nodeType === 1 && (c.tagName === 'UL' || c.tagName === 'OL')) {
          _docxWalk(c, blocks, listDepth + 1, c.tagName === 'OL');
        }
      }
    } else if (tag === 'TABLE') {
      var rows = [];
      var trs = el.querySelectorAll('tr');
      for (var r = 0; r < trs.length; r++) {
        var cells = [], cs = trs[r].children;
        for (var c2 = 0; c2 < cs.length; c2++) {
          var cell = cs[c2];
          if (cell.tagName !== 'TD' && cell.tagName !== 'TH') continue;
          cells.push({ header: cell.tagName === 'TH', runs: _docxTrimRuns(_docxInlineRuns(cell, false, false, [])) });
        }
        if (cells.length) rows.push(cells);
      }
      if (rows.length) blocks.push({ type: 'table', rows: rows });
    } else {
      _docxWalk(el, blocks, listDepth, ordered); // div etc: transparent container
    }
  }
  return blocks;
}

function _docxRunsXml(runs) {
  var out = '';
  for (var i = 0; i < (runs || []).length; i++) {
    var run = runs[i];
    var rpr = '';
    if (run.bold) rpr += '<w:b/><w:bCs/>';
    if (run.italic) rpr += '<w:i/><w:iCs/>';
    rpr = rpr ? '<w:rPr>' + rpr + '</w:rPr>' : '';
    var parts = String(run.text).split('\n'), pieces = '';
    for (var j = 0; j < parts.length; j++) {
      if (j) pieces += '<w:br/>';
      if (parts[j]) pieces += '<w:t xml:space="preserve">' + _docxEsc(parts[j]) + '</w:t>';
    }
    if (pieces) out += '<w:r>' + rpr + pieces + '</w:r>';
  }
  return out;
}

function _docxPara(runs, style, numId, level) {
  var ppr = '';
  if (style) ppr += '<w:pStyle w:val="' + style + '"/>';
  if (numId) ppr += '<w:numPr><w:ilvl w:val="' + (level || 0) + '"/><w:numId w:val="' + numId + '"/></w:numPr>';
  ppr = ppr ? '<w:pPr>' + ppr + '</w:pPr>' : '';
  return '<w:p>' + ppr + _docxRunsXml(runs) + '</w:p>';
}

function _docxTable(rows) {
  var cols = 1, i;
  for (i = 0; i < rows.length; i++) cols = Math.max(cols, rows[i].length);
  var grid = '';
  for (i = 0; i < cols; i++) grid += '<w:gridCol w:w="' + Math.floor(9026 / cols) + '"/>';
  var edges = ['top', 'left', 'bottom', 'right', 'insideH', 'insideV'], borders = '<w:tblBorders>';
  for (i = 0; i < edges.length; i++) borders += '<w:' + edges[i] + ' w:val="single" w:sz="4" w:space="0" w:color="D0D5DD"/>';
  borders += '</w:tblBorders>';
  var tblPr = '<w:tblPr><w:tblW w:w="5000" w:type="pct"/>' + borders +
    '<w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>';
  var body = '';
  for (var r = 0; r < rows.length; r++) {
    var tr = '';
    for (var c = 0; c < rows[r].length; c++) {
      var cell = rows[r][c];
      var shade = cell.header ? '<w:shd w:val="clear" w:color="auto" w:fill="F1F5F9"/>' : '';
      var runs = cell.runs || [];
      if (cell.header) { runs = runs.map(function (x) { return { text: x.text, bold: true, italic: x.italic }; }); }
      tr += '<w:tc><w:tcPr><w:tcW w:w="0" w:type="auto"/>' + shade + '</w:tcPr>' + _docxPara(runs) + '</w:tc>';
    }
    body += '<w:tr>' + tr + '</w:tr>';
  }
  return '<w:tbl>' + tblPr + '<w:tblGrid>' + grid + '</w:tblGrid>' + body + '</w:tbl>';
}

function _docxDocumentXml(blocks, title, subtitle) {
  var parts = '';
  if (title) parts += _docxPara([{ text: title, bold: true }], 'Title');
  if (subtitle) parts += _docxPara([{ text: subtitle }], 'Subtitle');
  for (var i = 0; i < blocks.length; i++) {
    var b = blocks[i];
    if (b.type === 'heading') parts += _docxPara(b.runs, 'Heading' + b.level);
    else if (b.type === 'paragraph') parts += _docxPara(b.runs, 'BodyText');
    else if (b.type === 'listitem') parts += _docxPara(b.runs, 'ListParagraph', b.ordered ? 2 : 1, b.level || 0);
    else if (b.type === 'table') parts += _docxTable(b.rows) + '<w:p/>';
  }
  var sect = '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>' +
    '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="708" w:footer="708" w:gutter="0"/></w:sectPr>';
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' +
    parts + sect + '</w:body></w:document>';
}

function _docxStylesXml() {
  function h(lvl, size, color) {
    return '<w:style w:type="paragraph" w:styleId="Heading' + lvl + '"><w:name w:val="heading ' + lvl + '"/>' +
      '<w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/>' +
      '<w:pPr><w:keepNext/><w:spacing w:before="240" w:after="80"/></w:pPr>' +
      '<w:rPr><w:b/><w:color w:val="' + color + '"/><w:sz w:val="' + size + '"/></w:rPr></w:style>';
  }
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' +
    '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri"/><w:sz w:val="23"/><w:szCs w:val="23"/></w:rPr></w:rPrDefault>' +
    '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>' +
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>' +
    '<w:style w:type="paragraph" w:styleId="BodyText"><w:name w:val="Body Text"/><w:basedOn w:val="Normal"/></w:style>' +
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="80"/></w:pPr><w:rPr><w:b/><w:color w:val="352A86"/><w:sz w:val="44"/></w:rPr></w:style>' +
    '<w:style w:type="paragraph" w:styleId="Subtitle"><w:name w:val="Subtitle"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:color w:val="6B7280"/><w:sz w:val="20"/></w:rPr></w:style>' +
    '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="60"/><w:ind w:left="720"/></w:pPr></w:style>' +
    h(1, 30, '352A86') + h(2, 24, '352A86') + h(3, 23, '1D4ED8') + h(4, 23, '374151') + '</w:styles>';
}

function _docxNumberingXml() {
  var bullet = '', decimal = '', lvl;
  for (lvl = 0; lvl < 3; lvl++) {
    var ind = 720 + lvl * 360;
    bullet += '<w:lvl w:ilvl="' + lvl + '"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>' +
      '<w:pPr><w:ind w:left="' + ind + '" w:hanging="360"/></w:pPr><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr></w:lvl>';
    decimal += '<w:lvl w:ilvl="' + lvl + '"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%' + (lvl + 1) + '."/><w:lvlJc w:val="left"/>' +
      '<w:pPr><w:ind w:left="' + ind + '" w:hanging="360"/></w:pPr></w:lvl>';
  }
  return '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' +
    '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/>' + bullet + '</w:abstractNum>' +
    '<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="hybridMultilevel"/>' + decimal + '</w:abstractNum>' +
    '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>';
}

var _DOCX_CONTENT_TYPES = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
  '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
  '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
  '<Default Extension="xml" ContentType="application/xml"/>' +
  '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>' +
  '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>' +
  '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/></Types>';

var _DOCX_ROOT_RELS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
  '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>';

var _DOCX_DOC_RELS = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
  '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
  '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>' +
  '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/></Relationships>';

// Public: convert export HTML into a real .docx Blob.
function htmlToDocxBlob(html, title, subtitle) {
  var doc = new DOMParser().parseFromString(String(html || ''), 'text/html');
  var blocks = _docxWalk(doc.body, [], 0, false);
  var enc = new TextEncoder();
  var files = [
    { name: '[Content_Types].xml', data: enc.encode(_DOCX_CONTENT_TYPES) },
    { name: '_rels/.rels', data: enc.encode(_DOCX_ROOT_RELS) },
    { name: 'word/_rels/document.xml.rels', data: enc.encode(_DOCX_DOC_RELS) },
    { name: 'word/document.xml', data: enc.encode(_docxDocumentXml(blocks, title, subtitle)) },
    { name: 'word/styles.xml', data: enc.encode(_docxStylesXml()) },
    { name: 'word/numbering.xml', data: enc.encode(_docxNumberingXml()) }
  ];
  return new Blob([_docxZip(files)], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
}
