// Every element id in index.html is unique: getElementById returns only the
// first match, so a repeated id silently moves another control's wiring.
const assert = require('assert/strict'), fs = require('fs'), path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
const seen = new Map();
for (const match of html.matchAll(/\sid="([^"]+)"/g)) seen.set(match[1], (seen.get(match[1]) || 0) + 1);
const repeated = [...seen].filter(([, count]) => count > 1).map(([id]) => id);
assert.deepEqual(repeated, [], 'repeated ids in index.html: ' + repeated.join(', '));
assert(seen.has('peopleHRNext') && seen.has('peopleHRGoContacts'), 'HR people paging and its next step have their own ids');
console.log(`index.html ids: ${seen.size} unique, none repeated.`);
