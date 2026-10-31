import React, { useCallback, useMemo, useState } from 'react';
import { Background, Controls, MiniMap, ReactFlow, ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { AlertTriangle, ArrowDownToLine, ArrowUpFromLine, ExternalLink, Loader2, Network, RefreshCw, Search } from 'lucide-react';
import { analyzeRepositoryDependencies } from '../services/api';
import { findDependencyPath } from '../utils/dependencyGraph';

function DependencyExplorerPanel({ repoUrl, darkMode = false }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [language, setLanguage] = useState('ALL');
  const [maxFiles, setMaxFiles] = useState(250);
  const [showAllGraph, setShowAllGraph] = useState(false);
  const [selected, setSelected] = useState('');
  const [fromPath, setFromPath] = useState('');
  const [toPath, setToPath] = useState('');
  const [path, setPath] = useState([]);
  const [reversePath, setReversePath] = useState([]);
  const [pathChecked, setPathChecked] = useState(false);

  const analyze = useCallback(async (refresh = false) => {
    if (!repoUrl.trim()) return;
    setLoading(true);
    setError('');
    const result = await analyzeRepositoryDependencies(repoUrl.trim(), { refresh, maxFiles });
    if (result.success) {
      setData(result.data);
      const degrees = new Map(result.data.nodes.map((node) => [node.id, node.incoming_count + node.outgoing_count]));
      setSelected([...result.data.nodes].sort((left, right) => degrees.get(right.id) - degrees.get(left.id) || left.path.localeCompare(right.path))[0]?.id || '');
      setPath([]);
      setReversePath([]);
      setPathChecked(false);
    } else setError(result.error);
    setLoading(false);
  }, [repoUrl, maxFiles]);

  const visibleNodes = useMemo(() => (data?.nodes || []).filter((node) =>
    (language === 'ALL' || node.language === language) && node.path.toLowerCase().includes(search.toLowerCase())
  ), [data, language, search]);
  const graphNodes = useMemo(() => {
    if (showAllGraph || !selected) return visibleNodes;
    if (path.length > 1 || reversePath.length > 1) {
      const pathIds = new Set(path.length > 1 ? path : reversePath);
      return visibleNodes.filter((node) => pathIds.has(node.id));
    }
    const neighbors = (data?.edges || []).filter((edge) => edge.source === selected || edge.target === selected)
      .map((edge) => edge.source === selected ? edge.target : edge.source);
    const uniqueNeighbors = [...new Set(neighbors)].filter((id) => visibleNodes.some((node) => node.id === id)).sort();
    const focusedIds = new Set([selected, ...uniqueNeighbors.slice(0, 12)]);
    return visibleNodes.filter((node) => focusedIds.has(node.id));
  }, [visibleNodes, data, selected, path, reversePath, showAllGraph]);
  const visibleIds = useMemo(() => new Set(graphNodes.map((node) => node.id)), [graphNodes]);
  const highlightedEdges = useMemo(() => {
    const links = (route) => route.slice(1).map((target, i) => `${route[i]}=>${target}`);
    return new Set([...links(path), ...links(reversePath)]);
  }, [path, reversePath]);
  const selectedNode = data?.nodes.find((node) => node.id === selected);
  const connectedIn = new Set((data?.edges || []).filter((edge) => edge.target === selected).map((edge) => edge.source));
  const connectedOut = new Set((data?.edges || []).filter((edge) => edge.source === selected).map((edge) => edge.target));
  const cycles = new Set((data?.cycles || []).flatMap((cycle) => cycle.paths));

  const graph = useMemo(() => {
    const nodes = graphNodes.map((node, index) => {
      const inFocus = selected && connectedIn.has(node.id);
      const outFocus = selected && connectedOut.has(node.id);
      return {
        id: node.id,
        position: { x: (index % 3) * 240, y: Math.floor(index / 3) * 110 },
        data: { label: node.path.split('/').slice(-2).join('/') },
        style: {
          width: 190, borderRadius: 10, padding: 10, fontSize: 11,
          color: darkMode ? '#eee9f8' : '#30294f',
          background: darkMode
            ? node.id === selected ? '#3a2b50' : cycles.has(node.id) ? '#40243a' : '#211b2d'
            : node.id === selected ? '#eee7ff' : cycles.has(node.id) ? '#fbe3f5' : '#ffffff',
          border: `1px solid ${node.id === selected ? (darkMode ? '#a78bfa' : '#8b68ee') : cycles.has(node.id) ? (darkMode ? '#c778b0' : '#d875bd') : inFocus ? '#70bd8b' : outFocus ? '#7aa8e8' : (darkMode ? '#40364f' : '#ded8ed')}`,
          opacity: selected && node.id !== selected && !inFocus && !outFocus ? 0.55 : 1,
        },
      };
    });
    const groupedEdges = new Map();
    for (const edge of (data?.edges || []).filter((item) => visibleIds.has(item.source) && visibleIds.has(item.target))) {
      const key = `${edge.source}=>${edge.target}`;
      if (!groupedEdges.has(key)) groupedEdges.set(key, []);
      groupedEdges.get(key).push(edge);
    }
    const edges = [...groupedEdges.entries()].map(([key, group]) => {
      const edge = group[0];
      const isPath = highlightedEdges.has(key);
      const isOutgoing = selected && edge.source === selected;
      const isIncoming = selected && edge.target === selected;
      const isHighlighted = isPath || isOutgoing || isIncoming;
      return {
        id: key, source: edge.source, target: edge.target,
        label: group.length > 1 ? `${group.length} imports` : `L${edge.source_line}`,
        animated: isPath,
        style: {
          stroke: isPath ? '#8055e8' : isOutgoing ? '#6696df' : isIncoming ? '#56ad79' : '#bdb6cf',
          strokeWidth: isHighlighted ? 2 : 1,
          opacity: isHighlighted ? 0.95 : selected ? 0.08 : 0.22,
        },
          labelStyle: { fill: isHighlighted ? (darkMode ? '#ddd0f7' : '#4e3b81') : (darkMode ? '#9b91aa' : '#827c94'), fontSize: 9 },
      };
    });
    return { nodes, edges };
  }, [graphNodes, data, selected, connectedIn, connectedOut, highlightedEdges, visibleIds, cycles, darkMode]);

  const selectNode = useCallback((_, node) => { setSelected(node.id); setPath([]); setReversePath([]); setPathChecked(false); }, []);
  const runPathSearch = () => {
    const edges = data?.edges || [];
    const direct = findDependencyPath(edges, fromPath, toPath);
    const reverse = direct.length ? [] : findDependencyPath(edges, toPath, fromPath);
    setPath(direct);
    setReversePath(reverse);
    setPathChecked(true);
    setSelected(fromPath);
  };

  return <section id="dependency-explorer" className="scroll-mt-24 mt-6 rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-6 text-left">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div><h3 className="flex items-center gap-2 text-base font-semibold text-white"><Network className="h-4 w-4 text-cyan-400" />Dependency Explorer</h3><p className="mt-1 text-xs text-slate-400">Resolved local imports only. External packages are not file edges.</p></div>
      <button type="button" onClick={() => analyze(Boolean(data))} disabled={loading || !repoUrl.trim()} className="inline-flex items-center gap-2 rounded-lg border border-cyan-800/70 bg-cyan-950/30 px-3 py-2 text-xs font-medium text-cyan-200 disabled:opacity-50">{loading ? <Loader2 className="h-4 w-4 animate-spin" /> : data ? <RefreshCw className="h-4 w-4" /> : <Network className="h-4 w-4" />}{data ? 'Refresh graph' : 'Analyze dependencies'}</button>
    </div>
    {loading && <p role="status" className="mt-4 text-xs text-cyan-200">Reading cached source snapshot and resolving imports…</p>}
    {error && <p role="alert" className="mt-4 flex items-center gap-2 text-xs text-rose-300"><AlertTriangle className="h-4 w-4" />{error}</p>}
    {!data && !loading && !error && <p className="mt-4 rounded-lg border border-slate-800 bg-slate-950/50 p-3 text-xs text-slate-400">Analyze this repository to explore its detected file dependencies.</p>}
    {data && <>
      <div className="mt-4 grid gap-2 sm:grid-cols-4">
        {[[data.files_analyzed, 'Files analyzed'], [data.edges.length, 'Resolved imports'], [data.cycles.length, 'Circular groups'], [data.unresolved_imports.length, 'Unresolved local imports']].map(([count, title]) => <div key={title} className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2"><p className="text-lg font-semibold text-slate-100">{count}</p><p className="text-[10px] text-slate-500">{title}</p></div>)}
      </div>
      {data.files_truncated && <p role="status" className="mt-3 text-xs text-amber-300">Graph limited to {data.graph_limit} files of {data.total_source_files}. Search/filter the returned set or raise the API limit up to 500.</p>}
      <div className="mt-4 flex flex-wrap gap-2">
        <label className="relative min-w-48 flex-1"><Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filter files…" className="w-full rounded-lg border border-slate-700 bg-slate-950 py-2 pl-8 pr-3 text-xs text-white outline-none focus:border-cyan-500" /></label>
        <select value={language} onChange={(event) => setLanguage(event.target.value)} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200"><option value="ALL">All languages</option>{data.languages.map((item) => <option key={item}>{item}</option>)}</select>
        <select aria-label="Graph file limit" value={maxFiles} onChange={(event) => setMaxFiles(Number(event.target.value))} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-200"><option value={250}>250 file limit</option><option value={500}>500 file limit</option></select>
        <label className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-300"><input type="checkbox" checked={showAllGraph} onChange={(event) => setShowAllGraph(event.target.checked)} />Show all files</label>
      </div>
      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_270px]">
        <div className="h-[480px] overflow-hidden rounded-xl border border-slate-800 bg-slate-950">
          {graphNodes.length ? <ReactFlowProvider key={graphNodes.map((node) => node.id).join('|')}><ReactFlow nodes={graph.nodes} edges={graph.edges} onNodeClick={selectNode} fitView fitViewOptions={{ padding: 0.2 }} minZoom={0.1} maxZoom={2}><Background color={darkMode ? '#2a2338' : '#ece7f6'} gap={22} /><MiniMap nodeColor={(node) => cycles.has(node.id) ? (darkMode ? '#9f4e8d' : '#e6a3d1') : node.id === selected ? '#9a80ed' : (darkMode ? '#55496b' : '#c8c2d7')} style={{ backgroundColor: darkMode ? '#171321' : '#f7f5fc' }} maskColor={darkMode ? 'rgba(13,10,20,.75)' : 'rgba(245,243,251,.75)'} /><Controls /></ReactFlow></ReactFlowProvider> : <div className="flex h-full items-center justify-center text-xs text-slate-500">No files match the current filters.</div>}
        </div>
        <p className="text-[10px] text-slate-500">Focused on {graphNodes.length} of {visibleNodes.length} matching files · select a node for its direct imports, or enable “Show all files”.</p>
        <aside className="space-y-3 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
          <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-400"><span className="inline-flex items-center gap-1"><ArrowDownToLine className="h-3 w-3 text-emerald-400" />incoming</span><span className="inline-flex items-center gap-1"><ArrowUpFromLine className="h-3 w-3 text-blue-400" />outgoing</span><span className="text-fuchsia-300">● cycle member</span></div>
          {selectedNode ? <><h4 className="break-all font-mono text-xs text-cyan-200">{selectedNode.path}</h4><p className="text-[10px] text-slate-500">{selectedNode.language} · {selectedNode.incoming_count} incoming · {selectedNode.outgoing_count} outgoing{selectedNode.isolated ? ' · isolated' : ''}</p><a href={selectedNode.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-[10px] text-cyan-300 hover:text-cyan-100">Open source file <ExternalLink className="h-3 w-3" /></a>
            <div><p className="mb-1 text-[10px] font-semibold uppercase text-slate-500">Imports (outgoing)</p>{data.edges.filter((edge) => edge.source === selected).map((edge) => <button key={edge.id} onClick={() => setSelected(edge.target)} className="block w-full truncate py-1 text-left font-mono text-[10px] text-blue-200 hover:text-white">{edge.target} <span className="text-slate-500">:{edge.source_line}</span></button>)}{!selectedNode.outgoing_count && <p className="text-[10px] text-slate-600">None detected</p>}</div>
            <div><p className="mb-1 text-[10px] font-semibold uppercase text-slate-500">Imported by (incoming)</p>{data.edges.filter((edge) => edge.target === selected).map((edge) => <button key={edge.id} onClick={() => setSelected(edge.source)} className="block w-full truncate py-1 text-left font-mono text-[10px] text-emerald-200 hover:text-white">{edge.source} <span className="text-slate-500">:{edge.source_line}</span></button>)}{!selectedNode.incoming_count && <p className="text-[10px] text-slate-600">None detected</p>}</div>
          </> : <p className="text-xs text-slate-500">Select a file node to inspect its dependencies and source link.</p>}
          <div className="border-t border-slate-800 pt-3"><p className="mb-2 text-[10px] font-semibold uppercase text-slate-500">Explore dependency path</p><select aria-label="Path start file" value={fromPath} onChange={(event) => { setFromPath(event.target.value); setPath([]); setReversePath([]); setPathChecked(false); }} className="mb-2 w-full rounded border border-slate-700 bg-slate-900 p-2 text-[10px] text-slate-200"><option value="">From file…</option>{data.nodes.map((node) => <option key={node.id} value={node.id}>{node.path}</option>)}</select><select aria-label="Path destination file" value={toPath} onChange={(event) => { setToPath(event.target.value); setPath([]); setReversePath([]); setPathChecked(false); }} className="mb-2 w-full rounded border border-slate-700 bg-slate-900 p-2 text-[10px] text-slate-200"><option value="">To file…</option>{data.nodes.map((node) => <option key={node.id} value={node.id}>{node.path}</option>)}</select><button onClick={runPathSearch} disabled={!fromPath || !toPath} className="w-full rounded border border-indigo-800 bg-indigo-950/40 p-2 text-[10px] text-indigo-200 disabled:opacity-40">Find path</button>{path.length > 1 ? <p className="mt-2 break-all text-[10px] leading-relaxed text-cyan-200">{path.join(' → ')}</p> : reversePath.length > 1 ? <p className="mt-2 break-all text-[10px] leading-relaxed text-amber-200">Only the reverse dependency path exists: {reversePath.join(' → ')}</p> : (path.length === 1 || reversePath.length === 1) ? <p className="mt-2 text-[10px] text-cyan-200">These selections are the same file.</p> : pathChecked && <p className="mt-2 text-[10px] text-amber-300">No local import path exists in either direction in the analyzed files.</p>}</div>
        </aside>
      </div>
      {!!data.cycles.length && <details className="mt-3 rounded-lg border border-fuchsia-900/50 bg-fuchsia-950/10 p-3"><summary className="cursor-pointer text-xs text-fuchsia-300">Circular dependency groups ({data.cycles.length})</summary><ul className="mt-2 max-h-32 space-y-1 overflow-auto">{data.cycles.map((cycle) => <li key={cycle.id} className="text-[10px] text-fuchsia-200/80">{cycle.paths.length} files: {cycle.paths.join(' ↔ ')}</li>)}</ul></details>}
      {!!data.unresolved_imports.length && <details className="mt-3 rounded-lg border border-amber-900/50 bg-amber-950/10 p-3"><summary className="cursor-pointer text-xs text-amber-200">Unresolved local imports ({data.unresolved_imports.length})</summary><ul className="mt-2 max-h-36 space-y-1 overflow-auto">{data.unresolved_imports.map((item) => <li key={`${item.source_path}:${item.source_line}:${item.imported_name}`} className="font-mono text-[10px] text-amber-100/80"><a href={item.source_url} target="_blank" rel="noreferrer" className="hover:underline">{item.source_path}:{item.source_line}</a> → {item.imported_name}</li>)}</ul></details>}
      <p className="mt-3 text-[10px] text-slate-600">Import locations and edges are detected from source text. External packages are not treated as unresolved local files.</p>
    </>}
  </section>;
}

export default function DependencyExplorer(props) {
  return <DependencyExplorerPanel {...props} />;
}
