/** Return the shortest directed file dependency path, if one exists. */
export function findDependencyPath(edges, start, end) {
  if (!start || !end) return [];
  const previous = new Map([[start, null]]);
  const queue = [start];
  for (let cursor = 0; cursor < queue.length; cursor += 1) {
    const current = queue[cursor];
    if (current === end) break;
    for (const edge of edges) {
      if (edge.source === current && !previous.has(edge.target)) {
        previous.set(edge.target, current);
        queue.push(edge.target);
      }
    }
  }
  if (!previous.has(end)) return [];
  const route = [];
  for (let current = end; current !== null; current = previous.get(current)) route.unshift(current);
  return route;
}
