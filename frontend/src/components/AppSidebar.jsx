import React from 'react';
import {
  Activity, BookOpen, ChevronDown, ChevronLeft, ChevronRight, Code2, FolderGit2,
  GitBranch, Home, LayoutDashboard, Network, Settings,
  Sparkles, Terminal, X,
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'home', label: 'Home', icon: Home },
  { id: 'ask', label: 'Ask RepoGuide', icon: Sparkles },
  { id: 'architecture', label: 'Architecture', icon: Network },
  { id: 'dependencies', label: 'Dependencies', icon: GitBranch },
  { id: 'dashboard', label: 'Q&A Dashboard', icon: LayoutDashboard },
];

export default function AppSidebar({ activePage, onNavigate, repoUrl, onSelectRepo, indexed, collapsed, onToggleCollapsed, mobileOpen, onCloseMobile }) {
  const repoName = repoUrl.replace(/^https?:\/\/(www\.)?github\.com\//i, '').replace(/\/$/, '') || 'Choose repository';
  const selectedExample = ['https://github.com/psf/requests', 'https://github.com/pallets/flask', 'https://github.com/fastapi/fastapi'].includes(repoUrl) ? repoUrl : 'custom';
  return <>
    {mobileOpen && <button aria-label="Close navigation" onClick={onCloseMobile} className="fixed inset-0 z-40 bg-[#12094d]/45 md:hidden" />}
    <aside className={`rg-sidebar fixed inset-y-0 left-0 z-50 flex flex-col text-white shadow-2xl shadow-violet-950/20 transition-all duration-200 ${collapsed ? 'md:w-[82px]' : 'md:w-[248px]'} w-[270px] ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
      <div className={`flex h-[76px] shrink-0 items-center ${collapsed ? 'justify-center px-3' : 'justify-between px-5'}`}>
        <button onClick={() => onNavigate('home')} className="flex min-w-0 items-center gap-3 text-left" aria-label="RepoGuide AI home">
          <span className="rg-sidebar-brand grid h-10 w-10 shrink-0 place-items-center rounded-[14px] border border-white/20 bg-gradient-to-br from-[#a18aff] to-[#6139dc] shadow-lg shadow-black/15"><Terminal className="h-5 w-5" /></span>
          {!collapsed && <span className="min-w-0"><b className="block truncate text-[16px] font-bold tracking-tight">RepoGuide AI</b><small className="mt-0.5 block truncate text-[10px] text-violet-200/80">Repository assistant</small></span>}
        </button>
        {!collapsed && <button onClick={onCloseMobile} className="rounded-lg p-1.5 text-violet-200 hover:bg-white/10 md:hidden"><X className="h-4 w-4" /></button>}
        {!collapsed && <button onClick={onToggleCollapsed} aria-label="Collapse sidebar" className="hidden rounded-lg p-1.5 text-violet-200 hover:bg-white/10 md:block"><ChevronLeft className="h-4 w-4" /></button>}
      </div>
      {collapsed && <button onClick={onToggleCollapsed} aria-label="Expand sidebar" className="mx-auto mb-2 hidden rounded-lg p-2 text-violet-200 hover:bg-white/10 md:block"><ChevronRight className="h-4 w-4" /></button>}

      <nav className="rg-sidebar-scroll flex-1 overflow-y-auto px-3 pb-4">
        <p className={`mb-2 mt-3 px-3 text-[9px] font-semibold uppercase tracking-[.16em] text-violet-300/55 ${collapsed ? 'text-center' : ''}`}>{collapsed ? '•••' : 'Workspace'}</p>
        <div className="space-y-1">{NAV_ITEMS.map(({ id, label, icon: Icon }) => {
          const active = activePage === id;
          return <button key={id} title={collapsed ? label : undefined} onClick={() => { onNavigate(id); onCloseMobile(); }} className={`rg-nav-item flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[12px] font-medium transition ${active ? 'rg-nav-active bg-gradient-to-r from-[#8b5cf6] to-[#6537df] text-white shadow-lg shadow-violet-950/20' : 'text-violet-100/80 hover:bg-white/10 hover:text-white'} ${collapsed ? 'justify-center' : ''}`}>
            <Icon className="h-[17px] w-[17px] shrink-0" /><span className={collapsed ? 'sr-only' : ''}>{label}</span>
          </button>;
        })}</div>

        <div className="my-5 border-t border-white/10" />
        <p className={`mb-2 px-3 text-[9px] font-semibold uppercase tracking-[.16em] text-violet-300/55 ${collapsed ? 'text-center' : ''}`}>{collapsed ? '•' : 'Repository'}</p>
        {!collapsed ? <div className="rg-sidebar-repository rounded-2xl border border-white/20 bg-white/[.08] p-3.5">
          <div className="mb-2 flex items-center gap-2"><FolderGit2 className="h-4 w-4 text-violet-200" /><span className="min-w-0 truncate text-[11px] font-semibold">{repoName}</span></div>
          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-[10px] text-emerald-300"><i className={`h-1.5 w-1.5 rounded-full ${indexed ? 'bg-emerald-300' : 'bg-amber-300'}`} />{indexed ? 'Indexed' : 'Not indexed'}</span>
            <label className="relative"><span className="sr-only">Select repository</span><select aria-label="Select repository" value={selectedExample} onChange={(event) => { if (event.target.value !== 'custom') onSelectRepo(event.target.value); else onNavigate('home'); }} className="max-w-[120px] appearance-none rounded-md border border-white/15 bg-[#241278] py-1 pl-2 pr-6 text-[9px] text-violet-100 outline-none"><option value="custom">Custom repo</option><option value="https://github.com/psf/requests">psf/requests</option><option value="https://github.com/pallets/flask">pallets/flask</option><option value="https://github.com/fastapi/fastapi">fastapi/fastapi</option></select><ChevronDown className="pointer-events-none absolute right-1.5 top-1.5 h-3 w-3 text-violet-200" /></label>
          </div>
        </div> : <button title={repoName} onClick={() => onNavigate('home')} className="mx-auto grid h-10 w-10 place-items-center rounded-xl border border-white/20 bg-white/10"><FolderGit2 className="h-4 w-4" /></button>}
      </nav>

      <div className="shrink-0 px-3 pb-4">
        {!collapsed && <div className="rg-sidebar-promo mb-4 rounded-2xl border border-violet-300/20 bg-gradient-to-br from-[#7043dc] to-[#4930ad] p-4 shadow-lg shadow-black/10">
          <div className="mb-3 grid h-9 w-9 place-items-center rounded-xl bg-white/15"><Code2 className="h-5 w-5 text-white" /></div>
          <p className="text-[12px] font-semibold">Understand every codebase</p><p className="mt-1.5 text-[10px] leading-relaxed text-violet-100/75">Explore structure, imports, and answers grounded in source.</p>
        </div>}
        <div className="mb-3 border-t border-white/10" />
        <button title={collapsed ? 'Settings' : undefined} onClick={() => { onNavigate('settings'); onCloseMobile(); }} className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[11px] text-violet-100/80 hover:bg-white/10 hover:text-white ${collapsed ? 'justify-center' : ''}`}><Settings className="h-4 w-4" /><span className={collapsed ? 'sr-only' : ''}>Settings</span></button>
        <a title={collapsed ? 'Documentation' : undefined} href={`${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/docs`} target="_blank" rel="noreferrer" className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[11px] text-violet-100/80 hover:bg-white/10 hover:text-white ${collapsed ? 'justify-center' : ''}`}><BookOpen className="h-4 w-4" /><span className={collapsed ? 'sr-only' : ''}>Documentation</span><Activity className={`ml-auto h-3.5 w-3.5 ${collapsed ? 'hidden' : ''}`} /></a>
      </div>
    </aside>
  </>;
}
