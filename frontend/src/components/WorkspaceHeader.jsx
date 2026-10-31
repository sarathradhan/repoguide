import React, { useEffect, useRef } from 'react';
import { Bell, Command, Menu, Moon, Search, Sun } from 'lucide-react';

const TITLES = {
  home: ['Home', 'Explore, understand, and get answers from your repositories.'],
  ask: ['Ask RepoGuide', 'Ask grounded questions and continue repository conversations.'],
  architecture: ['Architecture', 'Explore detected modules, routes, services, and integrations.'],
  dependencies: ['Dependencies', 'Trace source-backed imports and file relationships.'],
  dashboard: ['Q&A Dashboard', 'Repository activity and session-scoped insights.'],
  settings: ['Settings', 'Manage your current workspace and repository context.'],
};

export default function WorkspaceHeader({ page, onMobileMenu, search, setSearch, onSubmitSearch, repoUrl, theme = 'light', onToggleTheme }) {
  const searchRef = useRef(null);
  useEffect(() => {
    const handleShortcut = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleShortcut);
    return () => window.removeEventListener('keydown', handleShortcut);
  }, []);
  const [title, subtitle] = TITLES[page] || TITLES.home;
  const avatar = repoUrl.match(/github\.com\/(?:www\.)?([^/]+)/i)?.[1]?.[0]?.toUpperCase() || 'R';
  return <header className="rg-header sticky top-0 z-30 border-b border-[#e9e5f4] bg-white/90 backdrop-blur-xl">
    <div className="flex min-h-[72px] items-center gap-3 px-4 sm:px-6 lg:px-8">
      <button onClick={onMobileMenu} aria-label="Open navigation" className="rounded-xl border border-[#e9e5f4] p-2.5 text-[#51467b] hover:bg-[#f6f3ff] md:hidden"><Menu className="h-4 w-4" /></button>
      <div className="min-w-0 flex-1"><h1 className="truncate text-[16px] font-bold tracking-tight text-[#191638] sm:text-[18px]">{title}</h1><p className="mt-0.5 hidden truncate text-[10px] text-[#817d98] sm:block">{subtitle}</p></div>
      <form onSubmit={onSubmitSearch} className="hidden max-w-[420px] flex-1 items-center gap-2 rounded-xl border border-[#e5e0f2] bg-[#fbfaff] px-3 py-2 sm:flex">
        <Search className="h-4 w-4 shrink-0 text-[#85809e]" /><input ref={searchRef} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search repos, files, or ask a question…" className="min-w-0 flex-1 bg-transparent text-[11px] text-[#282347] outline-none placeholder:text-[#9a96ab]" aria-label="Global repository search" />
        <span className="inline-flex shrink-0 items-center gap-1 rounded-md border border-[#e4dff0] bg-white px-1.5 py-1 text-[9px] text-[#88839d]"><Command className="h-2.5 w-2.5" /> K</span>
      </form>
      <button type="button" onClick={onToggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`} className="rounded-xl border border-[#e9e5f4] p-2.5 text-[#51467b] hover:bg-[#f2edff] dark-mode-toggle">{theme === 'dark' ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
      <button aria-label="Notifications" className="hidden rounded-xl p-2.5 text-[#51467b] hover:bg-[#f2edff] sm:block"><Bell className="h-[17px] w-[17px]" /></button>
      <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-[#a17cff] to-[#6035e6] text-[12px] font-bold text-white shadow-md shadow-violet-300/50">{avatar}</span>
    </div>
    <form onSubmit={onSubmitSearch} className="flex items-center gap-2 px-4 pb-3 sm:hidden"><Search className="h-4 w-4 text-[#85809e]" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search repositories or ask…" className="min-w-0 flex-1 rounded-lg border border-[#e5e0f2] bg-[#fbfaff] px-3 py-2 text-xs outline-none" /><button type="submit" className="rounded-lg bg-[#6940e8] px-3 py-2 text-xs font-medium text-white">Go</button></form>
  </header>;
}
