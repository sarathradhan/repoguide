import React, { useEffect, useMemo, useState } from 'react';
import { ReactFlow, Background, Controls, Handle, MiniMap, Position } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { AlertTriangle, ExternalLink, Loader2, Network, RefreshCw, Search } from 'lucide-react';
import { analyzeRepositoryArchitecture } from '../services/api';

const COMPONENT_COLORS = {
  repository: 'border-cyan-500/70 bg-cyan-950/90',
  directory: 'border-slate-600 bg-slate-900/95',
  module: 'border-blue-500/60 bg-blue-950/90',
  entry_point: 'border-amber-500/70 bg-amber-950/90',
  route: 'border-violet-500/70 bg-violet-950/90',
  controller: 'border-fuchsia-500/70 bg-fuchsia-950/90',
  service: 'border-indigo-500/70 bg-indigo-950/90',
  database: 'border-emerald-500/70 bg-emerald-950/90',
  integration: 'border-orange-500/70 bg-orange-950/90',
};

function ArchitectureNode({ data }) {
  const color = COMPONENT_COLORS[data.componentType] || COMPONENT_COLORS.module;
  return (
    <div className={`min-w-44 max-w-64 rounded-xl border px-3 py-2.5 shadow-lg ${color} ${data.evidenceType === 'inferred' ? 'border-dashed' : ''}`}>
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-slate-300" />
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate text-xs font-semibold text-slate-100" title={data.label}>{data.label}</p>
          {data.path && <p className="mt-1 truncate font-mono text-[9px] text-slate-400" title={data.path}>{data.path}</p>}
        </div>
        <span className="shrink-0 rounded bg-black/25 px-1.5 py-0.5 text-[8px] uppercase tracking-wide text-slate-300">{data.componentType.replace('_', ' ')}</span>
      </div>
      <p className={`mt-2 text-[9px] ${data.evidenceType === 'inferred' ? 'text-amber-200' : 'text-emerald-200'}`}>
        {data.evidenceType === 'inferred' ? 'Inferred' : 'Detected'}
      </p>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-slate-300" />
    </div>
  );
}

const nodeTypes = { architecture: ArchitectureNode };

function getColumn(componentType) {
  if (componentType === 'repository') return 0;
  if (componentType === 'directory') return 1;
  if (['module', 'entry_point'].includes(componentType)) return 2;
  return 3;
}

export default function ArchitectureVisualizer({ repoUrl }) {
  const [architecture, setArchitecture] = useState(null);
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState('');
  const [showAllModules, setShowAllModules] = useState(false);
  const [showAllRelationships, setShowAllRelationships] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setArchitecture(null);
    setSelected(null);
    setError(null);
    setFilter('');
    setShowAllModules(false);
    setShowAllRelationships(false);
  }, [repoUrl]);

  const analyze = async (refresh = false) => {
    if (!repoUrl.trim() || loading) return;
    setLoading(true);
    setError(null);
    const result = await analyzeRepositoryArchitecture(repoUrl.trim(), refresh);
    if (result.success) {
      setArchitecture(result.data);
      setSelected(result.data.components[0] || null);
      setFilter('');
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  const { nodes, edges } = useMemo(() => {
    if (!architecture) return { nodes: [], edges: [] };
    const query = filter.trim().toLowerCase();
    const visibleComponents = architecture.components.filter((component) => {
      const matches = !query || `${component.label} ${component.path || ''} ${component.component_type} ${component.description}`.toLowerCase().includes(query);
      const ordinaryFile = component.component_type === 'module';
      return matches && (showAllModules || !ordinaryFile || Boolean(query));
    });
    const visibleIds = new Set(visibleComponents.map((component) => component.id));
    const rowByColumn = new Map();
    const layoutNodes = visibleComponents.map((component) => {
      const column = getColumn(component.component_type);
      const row = rowByColumn.get(column) || 0;
      rowByColumn.set(column, row + 1);
      return {
        id: component.id,
        type: 'architecture',
        position: { x: column * 300, y: row * 112 },
        data: {
          label: component.label,
          path: component.path,
          componentType: component.component_type,
          evidenceType: component.evidence_type,
        },
      };
    });
    const layoutEdges = architecture.relationships
      .filter((relationship) => visibleIds.has(relationship.source) && visibleIds.has(relationship.target))
      .filter((relationship) => showAllRelationships || relationship.source === selected?.id || relationship.target === selected?.id)
      .map((relationship) => ({
        id: relationship.id,
        source: relationship.source,
        target: relationship.target,
        label: showAllRelationships ? relationship.label : undefined,
        animated: false,
        style: {
          stroke: relationship.evidence_type === 'inferred' ? '#fbbf24' : '#38bdf8',
          strokeDasharray: relationship.evidence_type === 'inferred' ? '5 4' : undefined,
          strokeWidth: 1.25,
          opacity: showAllRelationships ? 0.42 : 0.8,
        },
        labelStyle: { fill: '#cbd5e1', fontSize: 9 },
        labelBgStyle: { fill: '#0f172a', fillOpacity: 0.95 },
        markerEnd: { type: 'arrowclosed', color: relationship.evidence_type === 'inferred' ? '#fbbf24' : '#38bdf8' },
      }));
    return { nodes: layoutNodes, edges: layoutEdges };
  }, [architecture, filter, selected, showAllModules, showAllRelationships]);

  const openSource = () => {
    if (selected?.source_url) window.open(selected.source_url, '_blank', 'noopener,noreferrer');
  };

  return (
    <section id="architecture-visualizer" className="scroll-mt-24 mt-6 rounded-2xl border border-slate-800 bg-slate-950/60 p-4 sm:p-5" aria-labelledby="architecture-heading">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="rounded-xl border border-cyan-900/70 bg-cyan-950/40 p-2 text-cyan-300"><Network className="h-5 w-5" /></div>
          <div>
            <h3 id="architecture-heading" className="text-base font-semibold text-white">Architecture visualizer</h3>
            <p className="mt-1 text-xs text-slate-400">Explore detected modules, entry points, routes, services, integrations, and their source-backed relationships.</p>
          </div>
        </div>
        <div className="flex gap-2">
          {architecture && <button type="button" onClick={() => analyze(true)} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:text-white disabled:opacity-50">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh files
          </button>}
          <button type="button" onClick={() => analyze(false)} disabled={loading || !repoUrl.trim()} className="inline-flex items-center gap-2 rounded-lg bg-cyan-700 px-3.5 py-2 text-xs font-semibold text-white hover:bg-cyan-600 disabled:opacity-50">
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Network className="h-3.5 w-3.5" />}
            {loading ? 'Analyzing…' : architecture ? 'Analyze cached files' : 'Analyze architecture'}
          </button>
        </div>
      </div>

      {loading && <div role="status" className="mt-4 flex items-center gap-2 rounded-lg border border-cyan-900/60 bg-cyan-950/20 px-3 py-3 text-xs text-cyan-200"><Loader2 className="h-4 w-4 animate-spin" /> Loading the saved source snapshot and extracting architecture facts…</div>}
      {error && <div role="alert" className="mt-4 flex items-start gap-2 rounded-lg border border-rose-900/70 bg-rose-950/30 px-3 py-3 text-xs text-rose-200"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />{error}</div>}
      {!architecture && !loading && !error && <p className="mt-4 rounded-lg border border-slate-800 bg-slate-900/50 px-3 py-3 text-xs text-slate-400">Run an analysis to map this repository. Existing ingestion/index snapshots are reused; refresh explicitly to fetch the latest files.</p>}
      {architecture && architecture.files_analyzed === 0 && !loading && <p role="status" className="mt-4 rounded-lg border border-amber-900/70 bg-amber-950/20 px-3 py-3 text-xs text-amber-200">No source files were available in this repository snapshot.</p>}
      {architecture && architecture.files_analyzed > 0 && <>
        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-[10px] text-slate-400">
          <span>{architecture.files_analyzed} files</span><span>{architecture.directories_detected} directories</span><span>{architecture.entry_points_detected} entry points</span><span>{architecture.routes_detected} routes</span>
          <span className="inline-flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-sky-400" />Detected relationship</span>
          <span className="inline-flex items-center gap-1.5"><i className="h-2 w-2 rounded-full bg-amber-400" />Inferred role/relationship</span>
        </div>
        {architecture.files_truncated && <p role="status" className="mt-3 rounded-lg border border-amber-900/70 bg-amber-950/20 px-3 py-2 text-[11px] text-amber-200">This map reflects the indexed/ingested file limit: {architecture.truncation_reason || 'some repository files were omitted'}.</p>}
        {architecture.entry_point_candidates > architecture.entry_points_detected && <p className="mt-2 text-[10px] text-amber-200">{architecture.entry_point_candidates - architecture.entry_points_detected} additional entry point candidate(s) are inferred from conventional filenames.</p>}
        <div className="mt-3 grid min-h-[560px] overflow-hidden rounded-xl border border-slate-800 bg-slate-950 xl:grid-cols-[minmax(0,1fr)_280px]">
          <div className="relative min-h-[560px]">
            <div className="absolute left-3 top-3 z-10 flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/95 px-2.5 py-2">
              <Search className="h-3.5 w-3.5 text-slate-500" />
              <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter components…" aria-label="Filter architecture components" className="w-40 bg-transparent text-xs text-slate-200 outline-none placeholder:text-slate-500" />
            </div>
            <div className="absolute right-3 top-3 z-10 flex flex-wrap gap-3 rounded-lg border border-slate-700 bg-slate-900/95 px-2.5 py-2 text-[10px] text-slate-300">
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={showAllModules} onChange={(event) => setShowAllModules(event.target.checked)} />All files ({architecture.components.filter((item) => item.component_type === 'module').length})</label>
              <label className="flex items-center gap-1.5"><input type="checkbox" checked={showAllRelationships} onChange={(event) => setShowAllRelationships(event.target.checked)} />All relationships</label>
            </div>
            {nodes.length ? <ReactFlow key={nodes.map((node) => node.id).join('|')} nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{ padding: 0.15 }} onNodeClick={(_, node) => setSelected(architecture.components.find((component) => component.id === node.id) || null)} proOptions={{ hideAttribution: true }}>
              <Background color="#263449" gap={24} size={1} /><Controls /><MiniMap nodeColor={(node) => node.data.evidenceType === 'inferred' ? '#f59e0b' : '#0e7490'} style={{ backgroundColor: '#0b1220' }} maskColor="rgba(2, 6, 23, 0.78)" />
            </ReactFlow> : <div className="flex h-full min-h-[560px] items-center justify-center px-6 text-center text-xs text-slate-500">No components match this filter.</div>}
            <p className="absolute bottom-3 left-3 z-10 rounded-md bg-slate-900/90 px-2 py-1 text-[10px] text-slate-400">Showing {nodes.length} components and {edges.length} focused relationships{!showAllModules ? ' · ordinary files hidden' : ''}</p>
          </div>
          <aside className="border-t border-slate-800 bg-slate-900/50 p-4 xl:border-l xl:border-t-0">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Component details</h4>
            {selected ? <div className="mt-3 space-y-3">
              <div><p className="break-words text-sm font-semibold text-white">{selected.label}</p><p className="mt-1 text-[10px] uppercase text-cyan-300">{selected.component_type.replace('_', ' ')} · {selected.evidence_type}</p></div>
              <p className="text-xs leading-relaxed text-slate-300">{selected.description}</p>
              {selected.path && <div><p className="text-[10px] uppercase text-slate-500">Source file</p><p className="mt-1 break-all font-mono text-[11px] text-slate-300">{selected.path}</p></div>}
              {selected.start_line && <p className="text-[11px] text-slate-400">Lines {selected.start_line}{selected.end_line && selected.end_line !== selected.start_line ? `–${selected.end_line}` : ''}{selected.language ? ` · ${selected.language}` : ''}</p>}
              {selected.details?.map((detail) => <p key={detail} className="text-[11px] text-slate-400">{detail}</p>)}
              {selected.source_url && <button type="button" onClick={openSource} className="inline-flex items-center gap-1.5 text-xs text-cyan-300 hover:text-cyan-100">Open source location <ExternalLink className="h-3 w-3" /></button>}
            </div> : <p className="mt-3 text-xs text-slate-500">Select a node to inspect its evidence and source location.</p>}
            {architecture.unsupported_files.length > 0 && <div className="mt-5 border-t border-slate-800 pt-3"><p className="text-[10px] font-semibold uppercase tracking-wide text-amber-300">Files not parsed ({architecture.unsupported_files.length})</p><p className="mt-1 text-[10px] leading-relaxed text-slate-500">{architecture.unsupported_files.slice(0, 6).join(', ')}{architecture.unsupported_files.length > 6 ? ` and ${architecture.unsupported_files.length - 6} more` : ''}</p></div>}
            {architecture.supported_languages.length > 0 && <p className="mt-4 text-[10px] text-slate-500">Parsers used: {architecture.supported_languages.join(', ')}</p>}
          </aside>
        </div>
      </>}
    </section>
  );
}
