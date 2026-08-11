'use strict';

// The frontend JS was extracted from the old monolithic index.html into
// vendor/cvstudio/*.js modules. Tests that search the frontend source for a
// function/definition/string must therefore look in index.html (still holds the
// markup + a small inline init) PLUS every module. This helper returns that
// combined source so a test finds each symbol wherever it was extracted to.
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

function frontendSource() {
  let source = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
  const moduleDir = path.join(ROOT, 'vendor', 'cvstudio');
  for (const name of fs.readdirSync(moduleDir).filter(f => f.endsWith('.js')).sort()) {
    source += '\n' + fs.readFileSync(path.join(moduleDir, name), 'utf8');
  }
  return source;
}

module.exports = { frontendSource, ROOT };
