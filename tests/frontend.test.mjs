import test from 'node:test';
import assert from 'node:assert/strict';
import {matchingOccurrences, monthCells, normalizedQuery, safeURL, archivePath} from '../site/core.mjs';

const p = {metadata:{doi:'10.1234/test'}, occurrences:[
  {date:'2026-11-24',title:'Nuclear condensates',topics:['LLPS'],keywords:['force'],summary:'摘要',editors_pick:true},
  {date:'2026-11-25',title:'Nuclear condensates revised',topics:['核力学'],keywords:['stiffness'],summary:'核力学摘要',editors_pick:false}
]};
test('DOI URL search and title or keyword search', () => {
  assert.equal(normalizedQuery('HTTPS://DOI.ORG/10.1234/TEST.'), '10.1234/test');
  assert.equal(matchingOccurrences(p,{query:'https://doi.org/10.1234/TEST'}).length,2);
  assert.equal(matchingOccurrences(p,{query:'condensates'}).length,2);
  assert.equal(matchingOccurrences(p,{query:'stiffness'}).length,1);
  assert.equal(matchingOccurrences(p,{query:'absent'}).length,0);
});
test('topic, search and picks apply to the same occurrence', () => {
  assert.equal(matchingOccurrences(p,{topic:'LLPS',pick:true}).length,1);
  assert.equal(matchingOccurrences(p,{topic:'核力学',pick:true}).length,0);
  assert.equal(matchingOccurrences(p,{topic:'LLPS',query:'stiffness'}).length,0);
});
test('Monday calendar and leap year without fabricating dates', () => {
  const cells = monthCells(2026,11);
  assert.equal(cells.filter(Boolean).length,30);
  assert.equal(cells.indexOf('2026-11-01'),6);
  assert.equal(monthCells(2028,2).filter(Boolean).length,29);
});
test('external links and history paths reject executable URLs and traversal', () => {
  assert.equal(safeURL('javascript:alert(1)'),null);
  assert.equal(safeURL('https://user:password@example.com'),null);
  assert.equal(safeURL('https://doi.org/10.1234/test'),'https://doi.org/10.1234/test');
  assert.ok(archivePath('archive/2026/11/2026-11-25.json'));
  assert.ok(archivePath(`history/2026-11-25/${'a'.repeat(64)}.json`));
  assert.equal(archivePath('../config.json'),false);
});
