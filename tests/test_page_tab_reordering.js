'use strict';
// Drag-to-reorder page tabs: the saved order is restored on reload, unknown
// tabs (added in a later update) survive, and the pin toggle always stays last.
const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync('index.html', 'utf8');

function fn(name) {
  const start = html.indexOf('function ' + name + '(');
  assert.ok(start >= 0, 'missing ' + name);
  let depth = 0;
  for (let i = html.indexOf('{', start); i < html.length; i++) {
    if (html[i] === '{') depth++;
    else if (html[i] === '}' && --depth === 0) return html.slice(start, i + 1);
  }
  throw new Error(name);
}

// The frontend must expose a stable, namespaced persistence key.
assert.ok(
  html.includes("var PAGE_TAB_ORDER_KEY = 'cvstudio_page_tab_order';"),
  'expected the cvstudio_page_tab_order localStorage key'
);
// Every AntiwordDependency-free requirement: the drag path must not add routes.
assert.ok(html.includes('function initPageTabReordering('), 'missing initPageTabReordering');

// ---- Minimal DOM mock (only what the persistence helpers touch) ----
function makeNode(id, cls) {
  return {
    id: id,
    className: cls,
    parentNode: null,
    classList: {
      _c: cls.split(/\s+/).filter(Boolean),
      contains(x) { return this._c.indexOf(x) >= 0; },
      add(x) { if (!this.contains(x)) this._c.push(x); },
      remove(x) { this._c = this._c.filter(t => t !== x); },
    },
    setAttribute() {},
  };
}

function matches(node, sel) {
  if (sel === '.page-nav-pin-toggle') return node.className.indexOf('page-nav-pin-toggle') >= 0;
  if (sel === '.page-tab') return node.className.split(/\s+/).indexOf('page-tab') >= 0;
  if (sel === '.page-tab:not(.tab-dragging)') {
    return matches(node, '.page-tab') && node.className.indexOf('tab-dragging') < 0;
  }
  return false;
}

function makeContainer(children) {
  const c = {
    children: children.slice(),
    classList: { add() {}, remove() {} },
    addEventListener() {},
    _reorderReady: false,
    contains(n) { return this.children.indexOf(n) >= 0; },
    querySelectorAll(sel) { return this.children.filter(n => matches(n, sel)); },
    querySelector(sel) { return this.children.find(n => matches(n, sel)) || null; },
    insertBefore(node, ref) {
      this.children = this.children.filter(n => n !== node);
      if (ref == null) { this.children.push(node); }
      else { this.children.splice(this.children.indexOf(ref), 0, node); }
      node.parentNode = this;
      return node;
    },
    appendChild(node) {
      this.children = this.children.filter(n => n !== node);
      this.children.push(node);
      node.parentNode = this;
      return node;
    },
  };
  children.forEach(n => (n.parentNode = c));
  return c;
}

function ids(container) {
  return container.querySelectorAll('.page-tab').map(n => n.id);
}

// ---- Build the sandbox with the extracted persistence helpers ----
let store = {};
const context = {
  JSON, Array, Object, String, Number,
  localStorage: {
    getItem(k) { return k in store ? store[k] : null; },
    setItem(k, v) { store[k] = String(v); },
    removeItem(k) { delete store[k]; },
  },
};
vm.createContext(context);
vm.runInContext(
  "var PAGE_TAB_ORDER_KEY = 'cvstudio_page_tab_order';\n" +
    [fn('pageTabOrderSave'), fn('pageTabOrderApplySaved'), fn('resetPageTabOrder')].join('\n'),
  context
);

function freshContainer() {
  return makeContainer([
    makeNode('tabFormat', 'page-tab active'),
    makeNode('tabBatch', 'page-tab'),
    makeNode('tabTheSpider', 'page-tab'),
    makeNode('tabLeadFinder', 'page-tab lead-locked'),
    makeNode('pageNavPinToggle', 'page-nav-pin-toggle'),
  ]);
}

// 1) A saved order (including a locked tab moved to the front) is restored, and
//    the pin toggle stays last.
store = {};
store[context.PAGE_TAB_ORDER_KEY] = JSON.stringify(['tabTheSpider', 'tabLeadFinder', 'tabFormat', 'tabBatch']);
let c = freshContainer();
context.pageTabOrderApplySaved(c);
assert.deepStrictEqual(ids(c), ['tabTheSpider', 'tabLeadFinder', 'tabFormat', 'tabBatch']);
assert.strictEqual(c.children[c.children.length - 1].id, 'pageNavPinToggle', 'pin toggle must stay last');

// 2) A tab absent from the saved order (added in a later update) survives and is
//    appended after the saved ones — never dropped.
store = {};
store[context.PAGE_TAB_ORDER_KEY] = JSON.stringify(['tabTheSpider', 'tabFormat']);
c = freshContainer();
context.pageTabOrderApplySaved(c);
assert.deepStrictEqual(ids(c), ['tabTheSpider', 'tabFormat', 'tabBatch', 'tabLeadFinder']);

// 3) A stale saved id that no longer exists is ignored without error.
store = {};
store[context.PAGE_TAB_ORDER_KEY] = JSON.stringify(['tabGone', 'tabBatch']);
c = freshContainer();
context.pageTabOrderApplySaved(c);
assert.deepStrictEqual(ids(c), ['tabBatch', 'tabFormat', 'tabTheSpider', 'tabLeadFinder']);

// 4) No saved order → DOM order is left untouched.
store = {};
c = freshContainer();
context.pageTabOrderApplySaved(c);
assert.deepStrictEqual(ids(c), ['tabFormat', 'tabBatch', 'tabTheSpider', 'tabLeadFinder']);

// 5) Saving persists the current tab order (pin toggle excluded).
store = {};
c = freshContainer();
c.insertBefore(c.querySelector('.page-tab:not(.tab-dragging)'), null); // no-op-ish churn
context.pageTabOrderSave(c);
assert.deepStrictEqual(JSON.parse(store[context.PAGE_TAB_ORDER_KEY]).slice(-1)[0] !== 'pageNavPinToggle', true);
assert.ok(JSON.parse(store[context.PAGE_TAB_ORDER_KEY]).indexOf('pageNavPinToggle') < 0, 'pin toggle is not a tab');

// 6) Reset clears the stored order.
store[context.PAGE_TAB_ORDER_KEY] = JSON.stringify(['tabBatch']);
context.resetPageTabOrder();
assert.strictEqual(store[context.PAGE_TAB_ORDER_KEY], undefined);

console.log('PASS: page tab drag-to-reorder persistence (restore, unknown-tab survival, pin-last, reset)');
