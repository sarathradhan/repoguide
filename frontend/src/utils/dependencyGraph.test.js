import assert from 'node:assert/strict';
import test from 'node:test';
import { findDependencyPath } from './dependencyGraph.js';

test('finds the shortest directed path', () => {
  const edges = [
    { source: 'a.py', target: 'b.py' },
    { source: 'b.py', target: 'c.py' },
    { source: 'a.py', target: 'c.py' },
  ];
  assert.deepEqual(findDependencyPath(edges, 'a.py', 'c.py'), ['a.py', 'c.py']);
});

test('does not traverse dependencies backwards', () => {
  assert.deepEqual(findDependencyPath([{ source: 'b.py', target: 'a.py' }], 'a.py', 'b.py'), []);
});

test('handles cycles without looping and reports disconnected files', () => {
  const edges = [
    { source: 'a.py', target: 'b.py' },
    { source: 'b.py', target: 'a.py' },
    { source: 'b.py', target: 'c.py' },
  ];
  assert.deepEqual(findDependencyPath(edges, 'a.py', 'c.py'), ['a.py', 'b.py', 'c.py']);
  assert.deepEqual(findDependencyPath(edges, 'a.py', 'isolated.py'), []);
});
