import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, BookOpen, Clock3, Code2, Database, GitBranch, Loader2, MessageSquare, Network, RefreshCw } from 'lucide-react';
import { getRepositoryDashboard } from '../services/api';

const STATUS_STYLES = {
  indexed: 'bg-emerald-950/60 text-emerald-300 border-emerald-800/70',
  indexing: 'bg-indigo-950/60 text-indigo-200 border-indigo-800/70',
  failed: 'bg-rose-950/60 text-rose-300 border-rose-800/70',
  empty: 'bg-amber-950/50 text-amber-200 border-amber-800/70',
  not_indexed: 'bg-slate-900 text-slate-400 border-slate-700',
};

function formatDate(value) {
  if (!value) return 'Not indexed yet';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Unknown' : date.toLocaleString();
}

function StatCard({ icon: Icon, label, value, hint }) {
  return <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3 sm:p-4">
    <div className="flex items-center justify-between gap-2"><span className="text-[10px] font-medium uppercase tracking-wide text-slate-500">{label}</span><Icon className="h-4 w-4 text-cyan-400" /></div>
    <p className="mt-2 text-xl font-semibold text-white">{value}</p>
    {hint && <p className="mt-1 text-[10px] text-slate-500">{hint}</p>}
  </div>;
}

export default function RepositoryDashboard({ repoUrl, sessionId, refreshKey = 0, isIndexing = false, onOpenConversation, onNavigate, onData, compact = false }) {
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!repoUrl?.trim() || !sessionId) return;
    setLoading(true);
    setError('');
    const result = await getRepositoryDashboard(repoUrl.trim(), sessionId);
    if (result.success) { setDashboard(result.data); onData?.(result.data); }
    else setError(result.error);
    setLoading(false);
  }, [repoUrl, sessionId, onData]);

  useEffect(() => { load(); }, [load, refreshKey]);

  const maxQuestions = useMemo(() => Math.max(1, ...(dashboard?.questions_over_time || []).map((day) => day.question_count)), [dashboard]);
  const languageTotal = useMemo(() => (dashboard?.languages || []).reduce((sum, item) => sum + item.files, 0), [dashboard]);
  const goTo = (page) => onNavigate?.(page);

  return <section id="repository-dashboard" className={`rg-dashboard rg-card text-left ${compact ? 'p-4 sm:p-5' : 'p-4 sm:p-6'}`} aria-labelledby="dashboard-title">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 id="dashboard-title" className="flex items-center gap-2 text-base font-semibold text-white"><Activity className="h-4 w-4 text-cyan-400" />{compact ? 'Repository overview' : 'Repository Q&A Dashboard'}</h3><p className="mt-1 text-xs text-slate-400">Repository metrics and questions saved in this browser session.</p></div>
      <button type="button" onClick={load} disabled={loading || !repoUrl?.trim()} className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-300 hover:text-white disabled:opacity-50">{loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}Refresh dashboard</button>
    </div>
    {!compact && <div className="mt-3 flex flex-wrap gap-2">
      <button onClick={() => goTo('ask')} className="rounded-lg border border-indigo-800/70 bg-indigo-950/30 px-3 py-2 text-[11px] text-indigo-200">Ask RepoGuide</button>
      <button onClick={() => goTo('architecture')} className="rounded-lg border border-cyan-800/70 bg-cyan-950/30 px-3 py-2 text-[11px] text-cyan-200">Architecture</button>
      <button onClick={() => goTo('dependencies')} className="rounded-lg border border-fuchsia-900/70 bg-fuchsia-950/20 px-3 py-2 text-[11px] text-fuchsia-200">Dependencies</button>
      <button onClick={() => document.getElementById('dashboard-conversations')?.scrollIntoView({ behavior: 'smooth', block: 'start' })} className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-[11px] text-slate-300">Previous conversations</button>
    </div>}
    {loading && !dashboard && <div role="status" className="mt-4 flex items-center gap-2 rounded-lg border border-cyan-900/50 bg-cyan-950/20 p-4 text-xs text-cyan-200"><Loader2 className="h-4 w-4 animate-spin" />Loading persisted repository and conversation data…</div>}
    {error && <div role="alert" className="mt-4 flex items-center justify-between gap-3 rounded-lg border border-rose-900/60 bg-rose-950/20 p-3 text-xs text-rose-200"><span className="flex items-center gap-2"><AlertTriangle className="h-4 w-4 shrink-0" />{error}</span><button onClick={load} className="shrink-0 underline">Retry</button></div>}
    {dashboard && <>
      <div className="mt-4 flex flex-col gap-3 rounded-xl border border-slate-800 bg-slate-950/50 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0"><a href={dashboard.repo_url} target="_blank" rel="noreferrer" className="break-all text-sm font-semibold text-cyan-200 hover:text-cyan-100">{dashboard.owner}/{dashboard.repository}</a>{dashboard.description && <p className="mt-1 line-clamp-2 text-xs text-slate-400">{dashboard.description}</p>}<p className="mt-1 text-[10px] text-slate-500">{dashboard.default_branch ? `Default branch: ${dashboard.default_branch} · ` : ''}{dashboard.snapshot_files} source files in saved snapshot</p></div>
        <span className={`w-fit rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase ${STATUS_STYLES[isIndexing ? 'indexing' : dashboard.indexing_status] || STATUS_STYLES.not_indexed}`}>{(isIndexing ? 'indexing' : dashboard.indexing_status).replace('_', ' ')}</span>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-4">
        <StatCard icon={Code2} label="Indexed files" value={dashboard.indexed_files} hint={`${dashboard.snapshot_files} files in snapshot`} />
        <StatCard icon={Database} label="Indexed chunks" value={dashboard.indexed_chunks} hint={`${dashboard.indexed_vectors} vectors stored`} />
        <StatCard icon={MessageSquare} label="Questions asked" value={dashboard.total_questions} hint="This repository · this session" />
        <StatCard icon={Clock3} label="Last indexed" value={dashboard.last_indexed_at ? formatDate(dashboard.last_indexed_at) : '—'} hint={dashboard.last_indexed_at ? 'Last successful index' : 'No successful index recorded'} />
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <section className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
          <h4 className="text-xs font-semibold text-slate-200">Questions over time <span className="font-normal text-slate-500">· last 30 days</span></h4>
          {dashboard.questions_over_time.length ? <div className="mt-4 flex h-28 items-end gap-1 border-b border-slate-800 pb-1" aria-label="Daily question counts">
            {dashboard.questions_over_time.map((day) => <div key={day.date} title={`${day.date}: ${day.question_count} question${day.question_count === 1 ? '' : 's'}`} className="group flex h-full min-w-1 flex-1 items-end justify-center">
              <div className="w-full max-w-5 rounded-t bg-cyan-500/75 transition-colors group-hover:bg-cyan-300" style={{ height: `${Math.max(5, (day.question_count / maxQuestions) * 100)}%` }} />
            </div>)}
          </div> : <p className="mt-4 rounded-lg border border-slate-800 p-3 text-xs text-slate-500">No questions recorded in the last 30 days.</p>}
          {dashboard.questions_over_time.length > 0 && <p className="mt-2 text-[10px] text-slate-500">{dashboard.questions_over_time[0].date} — {dashboard.questions_over_time.at(-1).date}</p>}
        </section>
        <section className="rounded-xl border border-slate-800 bg-slate-950/50 p-4">
          <h4 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><Code2 className="h-3.5 w-3.5 text-cyan-400" />Language distribution <span className="font-normal text-slate-500">· {dashboard.indexed_files ? 'indexed files' : 'saved snapshot files'}</span></h4>
          {dashboard.languages.length ? <><div className="mt-4 flex h-2 overflow-hidden rounded-full bg-slate-800">{dashboard.languages.map((item, index) => <div key={item.language} title={`${item.language}: ${item.files} files`} className={index % 3 === 0 ? 'bg-cyan-400' : index % 3 === 1 ? 'bg-indigo-400' : 'bg-emerald-400'} style={{ width: `${(item.files / languageTotal) * 100}%` }} />)}</div><div className="mt-3 flex flex-wrap gap-x-4 gap-y-2">{dashboard.languages.map((item, index) => <span key={item.language} className="inline-flex items-center gap-1.5 text-[10px] text-slate-400"><i className={`h-2 w-2 rounded-full ${index % 3 === 0 ? 'bg-cyan-400' : index % 3 === 1 ? 'bg-indigo-400' : 'bg-emerald-400'}`} />{item.language} <b className="text-slate-200">{item.files}</b></span>)}</div></> : <p className="mt-4 rounded-lg border border-slate-800 p-3 text-xs text-slate-500">No indexed language data is available yet.</p>}
        </section>
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-3">
        <section className="rounded-xl border border-slate-800 bg-slate-950/50 p-4"><h4 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><BookOpen className="h-3.5 w-3.5 text-cyan-400" />Frequently referenced files</h4>{dashboard.frequently_referenced_files.length ? <ul className="mt-3 space-y-2">{dashboard.frequently_referenced_files.slice(0, 5).map((file) => <li key={file.path} className="flex items-center justify-between gap-2 text-[10px]"><span className="truncate font-mono text-slate-300" title={file.path}>{file.path}</span><span className="shrink-0 text-cyan-300">{file.reference_count}</span></li>)}</ul> : <p className="mt-3 text-[11px] text-slate-500">No cited files yet.</p>}</section>
        <section className="rounded-xl border border-slate-800 bg-slate-950/50 p-4"><h4 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><GitBranch className="h-3.5 w-3.5 text-indigo-400" />Most explored modules</h4>{dashboard.most_explored_modules.length ? <ul className="mt-3 space-y-2">{dashboard.most_explored_modules.slice(0, 5).map((item) => <li key={item.path} className="flex items-center justify-between gap-2 text-[10px]"><span className="truncate font-mono text-slate-300">{item.path}</span><span className="shrink-0 text-indigo-300">{item.reference_count}</span></li>)}</ul> : <p className="mt-3 text-[11px] text-slate-500">Modules appear after answers cite source files.</p>}</section>
        <section className="rounded-xl border border-slate-800 bg-slate-950/50 p-4"><h4 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><ArrowUpRight className="h-3.5 w-3.5 text-amber-400" />Most explored topics</h4>{dashboard.most_explored_topics.length ? <div className="mt-3 flex flex-wrap gap-1.5">{dashboard.most_explored_topics.slice(0, 8).map((item) => <span key={item.topic} className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[10px] text-slate-300">{item.topic} <b className="text-amber-300">{item.question_count}</b></span>)}</div> : <p className="mt-3 text-[11px] text-slate-500">Topics appear after questions are asked.</p>}</section>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <section className="rounded-xl border border-slate-800 bg-slate-950/50 p-4"><h4 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><Network className="h-3.5 w-3.5 text-cyan-400" />Architecture overview</h4>{dashboard.architecture ? <p className="mt-3 text-[11px] leading-relaxed text-slate-400">{dashboard.architecture.files_analyzed} files · {dashboard.architecture.directories_detected} directories · {dashboard.architecture.entry_points_detected} entry points · {dashboard.architecture.routes_detected} routes detected</p> : <p className="mt-3 text-[11px] text-slate-500">No saved or indexed source snapshot is available for analysis.</p>}</section>
        <section className="rounded-xl border border-slate-800 bg-slate-950/50 p-4"><h4 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><GitBranch className="h-3.5 w-3.5 text-fuchsia-300" />Dependency overview</h4>{dashboard.dependencies ? <p className="mt-3 text-[11px] leading-relaxed text-slate-400">{dashboard.dependencies.files_analyzed} supported files · {dashboard.dependencies.resolved_imports} imports · {dashboard.dependencies.cycles} cycles · {dashboard.dependencies.unresolved_imports} unresolved · {dashboard.dependencies.isolated_files} isolated</p> : <p className="mt-3 text-[11px] text-slate-500">No saved or indexed source snapshot is available for analysis.</p>}</section>
      </div>

      <section className="mt-3 rounded-xl border border-slate-800 bg-slate-950/50 p-4"><h4 className="flex items-center gap-2 text-xs font-semibold text-slate-200"><ArrowDownRight className="h-3.5 w-3.5 text-cyan-400" />Recent Q&amp;A activity</h4>{dashboard.recent_activity.length ? <div className="mt-3 space-y-2">{dashboard.recent_activity.slice(0, 5).map((item) => <article key={`${item.conversation_id}:${item.created_at}`} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-[10px] text-slate-500">{item.conversation_title} · {formatDate(item.created_at)}</p><button onClick={() => onOpenConversation?.(item.conversation_id)} className="text-[10px] text-cyan-300 hover:text-cyan-100">Open conversation</button></div><p className="mt-2 text-xs font-medium text-slate-200">{item.question}</p>{item.answer_preview && <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-slate-400">{item.answer_preview}</p>}{item.sources.length > 0 && <p className="mt-2 truncate font-mono text-[10px] text-cyan-300">Cited: {item.sources.map((source) => `${source.path}:${source.start_line}-${source.end_line}`).join(' · ')}</p>}</article>)}</div> : <p className="mt-3 text-[11px] text-slate-500">No Q&amp;A activity is stored for this repository and browser session.</p>}</section>

      {!compact && <section id="dashboard-conversations" className="mt-3 rounded-xl border border-slate-800 bg-slate-950/50 p-4"><h4 className="text-xs font-semibold text-slate-200">Previous conversations <span className="font-normal text-slate-500">· this repository and browser session</span></h4>{dashboard.conversations.length ? <div className="mt-3 grid gap-2 md:grid-cols-2">{dashboard.conversations.slice(0, 10).map((conversation) => <button key={conversation.conversation_id} onClick={() => onOpenConversation?.(conversation.conversation_id)} className="rounded-lg border border-slate-800 bg-slate-900/50 p-3 text-left hover:border-cyan-900"><span className="block truncate text-xs font-medium text-slate-200">{conversation.title}</span><span className="mt-1 flex flex-wrap items-center gap-x-2 text-[10px] text-slate-500"><span>{dashboard.repository}</span><span>{conversation.message_count / 2} questions</span><span>{formatDate(conversation.updated_at)}</span></span></button>)}</div> : <p className="mt-3 text-[11px] text-slate-500">No saved conversations in this browser session yet.</p>}</section>}
    </>}
  </section>;
}
