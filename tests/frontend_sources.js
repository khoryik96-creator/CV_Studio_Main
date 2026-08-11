'use strict';

// The frontend JS was extracted from the old monolithic index.html into
// vendor/cvstudio/*.js modules. Tests that search the frontend source for a
// function/definition/string must look in index.html (still holds the markup +
// a small inline init) PLUS the modules it loads.
//
// The modules are read in the SAME ORDER as index.html's <script src> tags, and
// ONLY the files actually referenced there — not an alphabetical directory
// listing. Following the real load order means a test can only find a symbol if
// the browser actually loads the file that defines it; an orphaned or unused
// module file can never produce a false pass.
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const MODULE_TAG = /<script[^>]+src=["']\/vendor\/cvstudio\/([A-Za-z0-9._-]+\.js)(?:\?[^"']*)?["']/g;

function frontendSource() {
  const indexHtml = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
  let source = indexHtml;
  const seen = new Set();
  let match;
  while ((match = MODULE_TAG.exec(indexHtml))) {
    const name = match[1];
    if (seen.has(name)) continue;
    seen.add(name);
    const file = path.join(ROOT, 'vendor', 'cvstudio', name);
    if (fs.existsSync(file)) source += '\n' + fs.readFileSync(file, 'utf8');
  }
  return source;
}

module.exports = { frontendSource, ROOT };
