'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const source = fs.readFileSync(
  path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'ai-crawler.js'),
  'utf8'
);
const css = fs.readFileSync(
  path.resolve(__dirname, '..', 'vendor', 'cvstudio', 'app.css'),
  'utf8'
);

function sourceBlock(startMarker, endMarker) {
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start + startMarker.length);
  assert.ok(start >= 0, startMarker + ' must remain present');
  assert.ok(end > start, endMarker + ' must follow ' + startMarker);
  return source.slice(start, end);
}

const matching = sourceBlock(
  'function escapeTheSpiderRegex(',
  'function renderTheSpiderBooleanHighlights('
);
const context = {};
vm.runInNewContext(matching, context);

const htmlHighlighting = sourceBlock(
  'function clearTheSpiderHtmlHighlightMarks(',
  'function theSpiderVisualLayerWords('
);
vm.runInNewContext(htmlHighlighting, context);

const unusualText = 'Financial\u00a0reporting uses of\ufb01ce account-\ning controls.';
const phraseHits = context.findTheSpiderBooleanTermHits(
  unusualText,
  'Financial reporting'
);
assert.strictEqual(phraseHits.length, 1, 'NBSP must behave like normal spacing');
assert.strictEqual(
  unusualText.slice(phraseHits[0].start, phraseHits[0].end),
  'Financial\u00a0reporting'
);

const ligatureHits = context.findTheSpiderBooleanTermHits(unusualText, 'office');
assert.strictEqual(ligatureHits.length, 1, 'NFKC ligatures must remain highlightable');
assert.strictEqual(
  unusualText.slice(ligatureHits[0].start, ligatureHits[0].end),
  'of\ufb01ce'
);

const wrappedHits = context.findTheSpiderBooleanTermHits(unusualText, 'accounting');
assert.strictEqual(wrappedHits.length, 1, 'line-wrap hyphenation must not hide a term');
assert.strictEqual(
  unusualText.slice(wrappedHits[0].start, wrappedHits[0].end),
  'account-\ning'
);
assert.deepStrictEqual(
  Array.from(context.findTheSpiderBooleanTermHits('accountingx', 'accounting')),
  [],
  'normal word boundaries must remain protected'
);

function element(tagName, parentElement) {
  const node = {
    nodeType:1,
    tagName:tagName,
    parentElement:parentElement || null,
    parentNode:parentElement || null,
    childNodes:[],
    attributes:{},
    setAttribute:function(name, value){ this.attributes[name] = String(value); },
    getAttribute:function(name){ return this.attributes[name] || ''; },
    appendChild:function(child){
      if (child.parentNode) {
        const oldIndex = child.parentNode.childNodes.indexOf(child);
        if (oldIndex >= 0) child.parentNode.childNodes.splice(oldIndex, 1);
      }
      child.parentNode = this;
      child.parentElement = this;
      this.childNodes.push(child);
      return child;
    },
    replaceChild:function(next, previous){
      const index = this.childNodes.indexOf(previous);
      assert.ok(index >= 0, 'replacement node must belong to its parent');
      this.childNodes[index] = next;
      next.parentNode = this;
      next.parentElement = this;
      previous.parentNode = null;
      previous.parentElement = null;
      return previous;
    },
    normalize:function(){}
  };
  Object.defineProperty(node, 'textContent', {
    get:function(){ return this.childNodes.map(function(child){ return child.textContent; }).join(''); }
  });
  return node;
}
function textNode(value, parentElement) {
  const node = {
    nodeType:3,
    nodeValue:value,
    parentElement:parentElement,
    parentNode:parentElement,
    splitText:function(offset){
      const suffix = textNode(String(this.nodeValue || '').slice(offset), this.parentElement);
      this.nodeValue = String(this.nodeValue || '').slice(0, offset);
      const index = this.parentNode.childNodes.indexOf(this);
      this.parentNode.childNodes.splice(index + 1, 0, suffix);
      return suffix;
    }
  };
  Object.defineProperty(node, 'textContent', {
    get:function(){ return String(this.nodeValue || ''); }
  });
  return node;
}
function descendants(node) {
  return [node].concat((node.childNodes || []).reduce(function(items, child){
    return items.concat(descendants(child));
  }, []));
}

const root = element('DIV');
const paragraph = element('P', root);
const strong = element('STRONG', paragraph);
const firstRun = textNode('Financial', strong);
const separator = textNode(' ', paragraph);
const secondRun = textNode('reporting', paragraph);
strong.childNodes.push(firstRun);
paragraph.childNodes.push(strong, separator, secondRun);
root.childNodes.push(paragraph);

const runGroups = context.theSpiderHtmlPreviewTextGroups(root);
assert.strictEqual(runGroups.length, 1, 'one Word paragraph must remain one highlight group');
assert.strictEqual(runGroups[0].text, 'Financial reporting');
const runPlan = context.buildTheSpiderHtmlBooleanHighlightPlan(
  runGroups,
  [{text:'Financial reporting',kind:'positive'}],
  1500
);
assert.strictEqual(runPlan.matches.length, 1, 'a phrase split across Word formatting runs must match once');
assert.strictEqual(runPlan.segments.length, 3, 'the cross-run match must map back to every visual text node');
assert.deepStrictEqual(
  Array.from(runPlan.segments.map(function(segment){ return [segment.start,segment.end]; })),
  [[0,9],[0,1],[0,9]]
);

context.document = {
  querySelector:function(){ return root; },
  querySelectorAll:function(){
    return descendants(root).filter(function(node){
      return node.tagName === 'MARK' && node.getAttribute('data-spider-html-highlight');
    });
  },
  createElement:function(tagName){ return element(String(tagName || '').toUpperCase()); },
  createTextNode:function(value){ return textNode(String(value || ''), null); }
};
const applied = context.applyTheSpiderHtmlBooleanHighlights([
  {text:'Financial reporting',kind:'positive'}
]);
const visualMarks = context.document.querySelectorAll();
assert.strictEqual(applied.matches.length, 1, 'the visual HTML highlighter must count one cross-run phrase');
assert.strictEqual(visualMarks.length, 3, 'every formatted fragment of the phrase must be marked in the DOM');
assert.strictEqual(visualMarks.map(function(mark){ return mark.textContent; }).join(''), 'Financial reporting');
context.clearTheSpiderHtmlHighlightMarks('boolean');
assert.strictEqual(context.document.querySelectorAll().length, 0, 'turning highlights off must restore unmarked text');
assert.strictEqual(root.textContent, 'Financial reporting', 'clearing marks must preserve the exact CV wording');

const oversizedRoot = element('DIV');
const oversizedParagraph = element('P', oversizedRoot);
const oversizedRun = textNode('x'.repeat(70000), oversizedParagraph);
oversizedParagraph.childNodes.push(oversizedRun);
oversizedRoot.childNodes.push(oversizedParagraph);
const boundedGroups = context.theSpiderHtmlPreviewTextGroups(oversizedRoot);
assert.strictEqual(boundedGroups[0].text.length, 60000, 'one oversized Word run must be capped at the total scan budget');
assert.strictEqual(boundedGroups[0].nodes[0].end, 60000, 'the node-to-highlight map must use the same cap');

assert.ok(
  source.includes('function applyTheSpiderHtmlBooleanHighlights(terms)') &&
    source.includes("data-spider-html-highlight', 'boolean'") &&
    source.includes('hasTheSpiderDirectVisualHighlightSurface()'),
  'DOCX/converted-DOC HTML previews must receive direct Boolean highlights'
);
assert.ok(
  css.includes('.spider-cv-doc-html mark.boolean-positive') &&
    css.includes('.spider-cv-doc-html mark.boolean-negative') &&
    css.includes('.spider-cv-doc-html mark.boolean-mixed'),
  'HTML preview highlights must keep the established positive/negative/mixed legend'
);

console.log('spider preview highlight reliability frontend tests passed');
