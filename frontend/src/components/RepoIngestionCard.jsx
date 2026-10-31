import React, { Suspense, useState, useMemo, useEffect } from 'react';
import { 
  GitBranch, 
  Star, 
  FileCode, 
  Files, 
  Search, 
  Copy, 
  Check, 
  ExternalLink, 
  AlertTriangle, 
  Loader2, 
  X, 
  Code2,
  Filter,
  Sparkles,
  MessageSquarePlus,
  GitFork,
  Network,
  BarChart3,
  ArrowRight,
  Moon,
  Sun,
} from 'lucide-react';
import { askRepository, indexRepository, ingestRepository, createConversation, listConversations, getConversation, getSuggestedQuestions } from '../services/api';
import AppSidebar from './AppSidebar';
import WorkspaceHeader from './WorkspaceHeader';
import AnswerMarkdown from './AnswerMarkdown';

const ArchitectureVisualizer = React.lazy(() => import('./ArchitectureVisualizer'));
const DependencyExplorer = React.lazy(() => import('./DependencyExplorer'));
const RepositoryDashboard = React.lazy(() => import('./RepositoryDashboard'));

const QUICK_EXAMPLES = [
  { name: 'psf/requests', url: 'https://github.com/psf/requests' },
  { name: 'pallets/flask', url: 'https://github.com/pallets/flask' },
  { name: 'fastapi/fastapi', url: 'https://github.com/fastapi/fastapi' },
];

function getLanguageColor(language) {
  switch (language) {
    case 'Python':
      return 'bg-emerald-950/70 text-emerald-400 border-emerald-800/60';
    case 'JavaScript':
      return 'bg-amber-950/70 text-amber-400 border-amber-800/60';
    case 'TypeScript':
      return 'bg-blue-950/70 text-blue-400 border-blue-800/60';
    case 'React JSX':
    case 'React TSX':
      return 'bg-cyan-950/70 text-cyan-400 border-cyan-800/60';
    case 'Java':
      return 'bg-orange-950/70 text-orange-400 border-orange-800/60';
    case 'C++':
    case 'C/C++ Header':
    case 'C++ Header':
      return 'bg-rose-950/70 text-rose-400 border-rose-800/60';
    case 'C#':
      return 'bg-purple-950/70 text-purple-400 border-purple-800/60';
    case 'HTML':
      return 'bg-red-950/70 text-red-400 border-red-800/60';
    case 'CSS':
      return 'bg-indigo-950/70 text-indigo-400 border-indigo-800/60';
    case 'JSON':
    case 'YAML':
      return 'bg-teal-950/70 text-teal-400 border-teal-800/60';
    case 'SQL':
      return 'bg-sky-950/70 text-sky-400 border-sky-800/60';
    default:
      return 'bg-slate-800 text-slate-300 border-slate-700';
  }
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}

function formatStars(count) {
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}k`;
  }
  return count.toLocaleString();
}

function getBrowserSessionId() {
  const key = 'repoguide-session-id';
  let id = window.localStorage.getItem(key);
  if (!id) {
    id = window.crypto?.randomUUID?.() || 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (char) => {
      const random = Math.floor(Math.random() * 16);
      return (char === 'x' ? random : (random & 0x3) | 0x8).toString(16);
    });
    window.localStorage.setItem(key, id);
  }
  return id;
}

export default function RepoIngestionCard() {
  const [theme, setTheme] = useState(() => window.localStorage.getItem('repoguide-theme') || 'light');
  const [activePage, setActivePage] = useState('home');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [globalSearch, setGlobalSearch] = useState('');
  const [dashboardData, setDashboardData] = useState(null);
  const [architectureVisited, setArchitectureVisited] = useState(false);
  const [dependenciesVisited, setDependenciesVisited] = useState(false);
  const [repoUrl, setRepoUrl] = useState('https://github.com/psf/requests');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [repoData, setRepoData] = useState(null);
  const [indexing, setIndexing] = useState(false);
  const [indexStats, setIndexStats] = useState(null);
  const [dashboardRefreshKey, setDashboardRefreshKey] = useState(0);
  const [indexError, setIndexError] = useState(null);
  const [question, setQuestion] = useState('How does authentication work?');
  const [asking, setAsking] = useState(false);
  const [messages, setMessages] = useState([]);
  const [sessionId] = useState(getBrowserSessionId);
  const [conversationId, setConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [suggestions, setSuggestions] = useState([]);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [conversationError, setConversationError] = useState(null);
  const [askError, setAskError] = useState(null);

  // File explorer filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('ALL');
  const [activeFile, setActiveFile] = useState(null);
  const [copiedCode, setCopiedCode] = useState(false);

  useEffect(() => {
    window.localStorage.setItem('repoguide-theme', theme);
    document.documentElement.style.colorScheme = theme;
  }, [theme]);

  useEffect(() => {
    const candidate = repoUrl.trim();
    if (!/^https?:\/\/(www\.)?github\.com\/[\w.-]+\/[\w.-]+/i.test(candidate)) {
      setMessages([]);
      setConversations([]);
      setSuggestions([]);
      setConversationId(null);
      setConversationLoading(false);
      return undefined;
    }
    setMessages([]);
    setConversations([]);
    setSuggestions([]);
    setConversationId(null);
    setConversationLoading(true);
    let active = true;
    const timer = window.setTimeout(async () => {
      setConversationLoading(true);
      setConversationError(null);
      const [listResult, suggestionResult] = await Promise.all([
        listConversations(candidate, sessionId),
        getSuggestedQuestions(candidate),
      ]);
      if (!active) return;
      let list = listResult.success ? listResult.data.conversations : [];
      setConversations(list);
      setSuggestions(suggestionResult.success ? suggestionResult.data.suggestions : []);
      let restored = false;
      if (list.length) {
        const detail = await getConversation(candidate, sessionId, list[0].conversation_id);
        if (active && detail.success) {
          setConversationId(detail.data.conversation_id);
          setMessages(detail.data.messages);
          restored = true;
        } else if (active && detail.status !== 404) {
          setConversationError(detail.error);
        }
        // A stale conversation row should not prevent the user from starting a new thread.
        if (!restored) list = [];
      }
      if (active && !restored) {
        const created = await createConversation(candidate, sessionId);
        if (active && created.success) {
          setConversationId(created.data.conversation_id);
          setMessages([]);
          setConversations([]);
          setConversationError(null);
        } else if (active && !created.success) {
          setConversationError(`Saved conversations are unavailable: ${created.error}. You can still ask questions; they will use this page's recent chat only.`);
        }
      }
      if (active) setConversationLoading(false);
    }, 400);
    return () => { active = false; window.clearTimeout(timer); };
  }, [repoUrl, sessionId]);

  const handleIngest = async (e) => {
    if (e) e.preventDefault();
    if (!repoUrl.trim() || loading) return;

    setLoading(true);
    setError(null);
    setActiveFile(null);

    const result = await ingestRepository(repoUrl.trim());

    if (result.success) {
      setRepoData(result.data);
      setDashboardRefreshKey((current) => current + 1);
      // Auto-select first file if available
      if (result.data.files && result.data.files.length > 0) {
        setActiveFile(result.data.files[0]);
      }
    } else {
      setError(result.error || 'Failed to ingest repository');
    }
    setLoading(false);
  };

  const handleIndex = async () => {
    if (!repoUrl.trim() || indexing) return;
    setIndexing(true);
    setIndexError(null);
    setIndexStats(null);
    const result = await indexRepository(repoUrl.trim());
    setDashboardRefreshKey((current) => current + 1);
    if (result.success) {
      setIndexStats(result.data);
      const suggested = await getSuggestedQuestions(repoUrl.trim());
      setSuggestions(suggested.success ? suggested.data.suggestions : []);
    }
    else setIndexError(result.error || 'Failed to index repository');
    setIndexing(false);
  };

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!repoUrl.trim() || !question.trim() || asking) return;
    setAsking(true);
    setAskError(null);
    const askedQuestion = question.trim();
    const recentHistory = messages
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .slice(-6)
      .map(({ role, content }) => ({ role, content }));
    const chatContext = conversationId
      ? { sessionId, conversationId }
      : { history: recentHistory };
    const result = await askRepository(repoUrl.trim(), askedQuestion, 5, chatContext);
    if (result.success) {
      const data = result.data;
      setDashboardRefreshKey((current) => current + 1);
      const timestamp = new Date().toISOString();
      setMessages((current) => [...current,
        { role: 'user', content: askedQuestion, created_at: timestamp, sources: [] },
        { role: 'assistant', content: data.answer, created_at: timestamp, sources: data.sources, retrieved_context: data.retrieved_context },
      ]);
      if (data.conversation_id) {
        setConversationId(data.conversation_id);
        setConversations((current) => {
          const exists = current.some((thread) => thread.conversation_id === data.conversation_id);
          if (!exists) return [{
            conversation_id: data.conversation_id,
            title: askedQuestion.slice(0, 80),
            message_count: 2,
            created_at: timestamp,
            updated_at: timestamp,
          }, ...current];
          return current.map((thread) => thread.conversation_id === data.conversation_id
            ? { ...thread, title: thread.message_count ? thread.title : askedQuestion.slice(0, 80), message_count: thread.message_count + 2, updated_at: timestamp }
            : thread);
        });
      }
      setQuestion('');
    } else {
      setAskError(result.error || 'Could not answer this repository question');
    }
    setAsking(false);
  };

  const handleNewConversation = async () => {
    const result = await createConversation(repoUrl.trim(), sessionId);
    if (!result.success) {
      setConversationError(`Could not create a saved conversation: ${result.error}. You can still ask questions without saved history.`);
      return;
    }
    setConversationId(result.data.conversation_id);
    setDashboardRefreshKey((current) => current + 1);
    setMessages([]);
    setConversationError(null);
    setConversations((current) => [
      { conversation_id: result.data.conversation_id, title: result.data.title, message_count: 0, created_at: result.data.created_at, updated_at: result.data.updated_at },
      ...current,
    ]);
  };

  const handleSelectConversation = async (id) => {
    const result = await getConversation(repoUrl.trim(), sessionId, id);
    if (!result.success) { setConversationError(result.error); return; }
    setConversationId(result.data.conversation_id);
    setMessages(result.data.messages);
    setConversationError(null);
  };

  // Compute distinct languages and counts from downloaded files
  const languageStats = useMemo(() => {
    if (!repoData?.files) return {};
    const stats = {};
    for (const f of repoData.files) {
      stats[f.language] = (stats[f.language] || 0) + 1;
    }
    return stats;
  }, [repoData]);

  // Filter files based on search query and language tag
  const filteredFiles = useMemo(() => {
    if (!repoData?.files) return [];
    return repoData.files.filter((file) => {
      const matchesSearch = file.path.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesLanguage = selectedLanguage === 'ALL' || file.language === selectedLanguage;
      return matchesSearch && matchesLanguage;
    });
  }, [repoData, searchQuery, selectedLanguage]);

  const handleCopyCode = () => {
    if (!activeFile) return;
    navigator.clipboard.writeText(activeFile.content);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const handleGlobalSearch = (event) => {
    event.preventDefault();
    const value = globalSearch.trim();
    if (!value) return;
    if (/^https?:\/\/github\.com\//i.test(value) || /^github\.com\//i.test(value)) {
      setRepoUrl(value.startsWith('http') ? value : `https://${value}`);
      navigatePage('home');
    } else {
      setQuestion(value);
      navigatePage('ask');
    }
    setGlobalSearch('');
  };

  const openConversationFromDashboard = async (id) => {
    await handleSelectConversation(id);
    navigatePage('ask');
  };

  const navigatePage = (page) => {
    setActivePage(page);
    if (page === 'architecture') setArchitectureVisited(true);
    if (page === 'dependencies') setDependenciesVisited(true);
  };

  const repoName = repoData ? `${repoData.owner}/${repoData.repository}` : repoUrl.replace(/^https?:\/\/(www\.)?github\.com\//i, '').replace(/\/$/, '') || 'Select a repository';

  return (
    <div className="rg-shell" data-theme={theme}>
      <AppSidebar
        activePage={activePage}
        onNavigate={navigatePage}
        repoUrl={repoUrl}
        onSelectRepo={(url) => { setRepoUrl(url); navigatePage('home'); }}
        indexed={dashboardData?.indexing_status === 'indexed' || Boolean(indexStats?.vectors_stored)}
        collapsed={sidebarCollapsed}
        onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
        mobileOpen={mobileNavOpen}
        onCloseMobile={() => setMobileNavOpen(false)}
      />
      <div className={`rg-workspace min-h-screen transition-[margin] duration-200 ${sidebarCollapsed ? 'md:ml-[82px]' : 'md:ml-[248px]'}`}>
        <WorkspaceHeader page={activePage} onMobileMenu={() => setMobileNavOpen(true)} search={globalSearch} setSearch={setGlobalSearch} onSubmitSearch={handleGlobalSearch} repoUrl={repoUrl} theme={theme} onToggleTheme={() => setTheme((value) => value === 'dark' ? 'light' : 'dark')} />
        <main className="rg-page">
      <div className="rg-feature-surface space-y-5">
        {activePage === 'home' && <>
          <div className="mb-1"><p className="text-[22px] font-bold tracking-tight text-[#191638]">Welcome back! <span aria-hidden="true">👋</span></p><p className="mt-1 text-[12px] text-[#77748f]">Explore, understand, and get grounded answers from your repositories.</p></div>
          <div className="grid grid-cols-2 gap-2.5 xl:grid-cols-4">
            {[
              { id: 'ask', title: 'Ask RepoGuide', caption: 'Chat with your codebase', icon: MessageSquarePlus, color: 'from-[#f3e8ff] to-[#e8eaff]', ink: 'text-violet-700' },
              { id: 'architecture', title: 'Architecture', caption: 'Visualize system structure', icon: Network, color: 'from-[#effbdc] to-[#e2f7ca]', ink: 'text-green-700' },
              { id: 'dependencies', title: 'Dependencies', caption: 'Explore file relationships', icon: GitBranch, color: 'from-[#fde7f7] to-[#fbd9f1]', ink: 'text-pink-700' },
              { id: 'dashboard', title: 'Q&A Dashboard', caption: 'Insights and activity', icon: BarChart3, color: 'from-[#fff4d9] to-[#ffedc5]', ink: 'text-amber-700' },
            ].map(({ id, title, caption, icon: Icon, color, ink }) => <button key={id} onClick={() => navigatePage(id)} className={`rg-feature-tile group flex min-h-[78px] items-center gap-3 rounded-2xl border border-white/80 bg-gradient-to-br ${color} p-3 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md sm:p-4`}>
              <span className={`grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white/70 ${ink}`}><Icon className="h-5 w-5" /></span><span className="min-w-0 flex-1"><b className="block truncate text-[11px] font-bold text-[#201b43] sm:text-[12px]">{title}</b><small className="mt-1 block truncate text-[9px] text-[#6f6a86] sm:text-[10px]">{caption}</small></span><ArrowRight className="h-4 w-4 shrink-0 text-[#51467b] transition group-hover:translate-x-0.5" />
            </button>)}
          </div>
        </>}
        {activePage === 'dashboard' && <div className="mb-1"><p className="text-[20px] font-bold tracking-tight text-[#191638]">Repository overview</p><p className="mt-1 text-[11px] text-[#77748f]">Live indexing metrics and Q&amp;A activity for {repoName}.</p></div>}
        {activePage === 'settings' && <section className="rg-card p-5 sm:p-7"><h2 className="text-lg font-bold">Workspace settings</h2><p className="mt-1 text-sm text-[#77748f]">Your browser session keeps conversations private to this browser and selected repository.</p><div className="mt-5 grid gap-3 sm:grid-cols-2"><div className="rg-card-soft p-4"><p className="text-[10px] uppercase tracking-wide text-[#85809b]">Selected repository</p><p className="mt-2 break-all text-sm font-semibold">{repoName}</p></div><div className="rg-card-soft p-4"><p className="text-[10px] uppercase tracking-wide text-[#85809b]">Workspace session</p><p className="mt-2 font-mono text-xs">{sessionId}</p></div></div></section>}
        {activePage === 'home' && <section className="rg-hero-panel rg-card overflow-hidden bg-gradient-to-r from-[#eee4ff] via-[#f5edff] to-[#eae8ff] p-5 sm:p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="grid h-10 w-10 place-items-center rounded-xl border border-white/70 bg-white/70 text-violet-700 shadow-sm">
            <GitFork className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-[18px] font-bold tracking-tight text-[#201b43]">Analyze a GitHub repository</h2>
            <p className="mt-1 text-[11px] text-[#6f6988]">Ingest, index, and explore any public repository with AI.</p>
          </div>
        </div>

        {/* Ingestion Form */}
        <form onSubmit={handleIngest} className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#635b82]">
                <GitFork className="h-4 w-4" />
              </div>
              <input
                type="text"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/owner/repository"
                disabled={loading}
                className="rg-input w-full pl-10 pr-10 py-3 text-[12px] placeholder:text-[#a09ab3] transition-colors disabled:opacity-50"
              />
              {repoUrl && !loading && (
                <button
                  type="button"
                  onClick={() => setRepoUrl('')}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-[#8983a0] hover:text-violet-700 transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || !repoUrl.trim()}
              className="rg-button-primary inline-flex items-center justify-center gap-2 px-5 py-3 text-[12px] font-semibold disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Ingesting Repository...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  <span>Analyze Repository</span>
                </>
              )}
            </button>
          </div>

          {/* Quick Examples */}
          <div className="flex items-center gap-2 flex-wrap pt-1 text-[10px] text-[#77748f]">
            <span>Try:</span>
            {QUICK_EXAMPLES.map((ex) => (
              <button
                key={ex.name}
                type="button"
                onClick={() => setRepoUrl(ex.url)}
                disabled={loading}
                className="rounded-full border border-white/80 bg-white/70 px-3 py-1.5 font-medium text-[#51467b] shadow-sm transition hover:border-violet-300 hover:text-violet-700"
              >
                {ex.name}
              </button>
            ))}
          </div>
        </form>
        </section>}

        {/* Milestone 3 index and Milestone 4 repository Q&A */}
        {activePage === 'home' && <section className="rg-card space-y-4 p-4 sm:p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <h3 className="text-base font-semibold text-white">Repository index</h3>
              <p className="text-xs text-slate-400 mt-1">Chunk, embed, and save source code in a repository-specific index for retrieval.</p>
            </div>
            <button type="button" onClick={handleIndex} disabled={indexing || loading || !repoUrl.trim()}
              className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-500 hover:bg-indigo-400 text-white text-sm font-semibold disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              {indexing ? <><Loader2 className="h-4 w-4 animate-spin" /> Indexing repository…</> : <><Sparkles className="h-4 w-4" /> Index repository</>}
            </button>
          </div>
          {indexing && <p className="text-xs text-indigo-300">Downloading source files, generating embeddings, and writing the persistent index. First run may take longer while the model loads.</p>}
          {indexError && <p role="alert" className="text-xs text-rose-300">{indexError}</p>}
          {indexStats && <div role="status" className="grid grid-cols-3 gap-2">
            {[['Files processed', indexStats.files_processed], ['Chunks created', indexStats.chunks_created], ['Vectors stored', indexStats.vectors_stored]].map(([label, value]) =>
              <div key={label} className="rounded-lg border border-indigo-900/70 bg-indigo-950/30 p-3 text-center"><div className="text-lg font-bold text-indigo-200">{value}</div><div className="text-[11px] text-slate-400">{label}</div></div>
            )}
          </div>}

        </section>}

          {(activePage === 'home' || activePage === 'dashboard') && <Suspense fallback={<p role="status" className="rg-card p-5 text-xs text-slate-400">Loading repository dashboard…</p>}>
            <RepositoryDashboard
              repoUrl={repoUrl}
              sessionId={sessionId}
              refreshKey={dashboardRefreshKey}
              isIndexing={indexing}
              onOpenConversation={openConversationFromDashboard}
              onNavigate={navigatePage}
              onData={setDashboardData}
              compact={activePage === 'home'}
              darkMode={theme === 'dark'}
            />
          </Suspense>}

          {activePage === 'ask' && <div id="ask-repoguide" className="rg-card scroll-mt-24 space-y-4 p-4 sm:p-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-white">Ask RepoGuide</h3>
                <p className="text-xs text-slate-400 mt-1">Conversations save in this browser and stay scoped to the selected repository.</p>
              </div>
              <div className="flex gap-2 min-w-0">
                <select value={conversationId || ''} onChange={(e) => handleSelectConversation(e.target.value)} aria-label="Conversation history"
                  className="min-w-0 flex-1 sm:max-w-56 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-300">
                  {conversationId && !conversations.some((thread) => thread.conversation_id === conversationId) && <option value={conversationId}>Current conversation</option>}
                  {conversations.map((thread) => <option key={thread.conversation_id} value={thread.conversation_id}>{thread.title}</option>)}
                </select>
                <button type="button" onClick={handleNewConversation} disabled={!repoUrl.trim() || conversationLoading}
                  className="shrink-0 inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-slate-700 bg-slate-900 text-slate-300 hover:text-white text-xs disabled:opacity-50">
                  <MessageSquarePlus className="h-3.5 w-3.5" /> New
                </button>
              </div>
            </div>
            {conversationLoading && <p role="status" className="text-xs text-slate-400">Restoring your repository conversations…</p>}
            {conversationError && <p role="alert" className="text-xs text-rose-300">{conversationError}</p>}
            {suggestions.length > 0 && <div className="flex flex-wrap gap-2" aria-label="Suggested repository questions">
              {suggestions.map((suggestion) => <button key={suggestion} type="button" onClick={() => setQuestion(suggestion)}
                className="px-2.5 py-1.5 rounded-lg border border-indigo-900/70 bg-indigo-950/30 text-[11px] text-indigo-200 hover:border-indigo-700">{suggestion}</button>)}
            </div>}
            <form onSubmit={handleAsk} className="flex flex-col sm:flex-row gap-3">
              <input value={question} onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question about this repository…" aria-label="Ask a question about this repository"
                className="min-w-0 flex-1 px-3.5 py-2.5 bg-slate-950 border border-slate-800 focus:border-indigo-500 rounded-xl text-sm text-slate-100 placeholder-slate-500 outline-none" />
              <button type="submit" disabled={asking || indexing || conversationLoading || !question.trim()}
                className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl border border-indigo-700 bg-indigo-950/70 hover:bg-indigo-900/70 text-indigo-200 text-sm font-semibold disabled:opacity-50">
                {asking ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} {asking ? 'Thinking…' : 'Ask RepoGuide'}
              </button>
            </form>
            {asking && <p role="status" className="text-xs text-indigo-300">Retrieving relevant code and preparing a grounded answer…</p>}
            {askError && <p role="alert" className="text-xs text-rose-300">{askError}</p>}
            {messages.length === 0 && !conversationLoading && <p className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-3 text-xs text-slate-500">Start with a suggested question or ask about any part of the indexed code. Answers with insufficient context will be labeled clearly.</p>}
            {messages.length > 0 && <div className="space-y-3" aria-live="polite">
              {messages.map((message, index) => message.role === 'user' ? (
                <div key={message.message_id || `user-${index}`} className="ml-auto max-w-[90%] rounded-xl border border-indigo-900/70 bg-indigo-950/40 px-4 py-3">
                  <p className="text-[10px] uppercase tracking-wide text-indigo-300">You asked</p>
                  <p className="mt-1 text-sm text-slate-100">{message.content}</p>
                </div>
              ) : (
                <article key={message.message_id || `assistant-${index}`} className="rounded-xl border border-slate-800 bg-slate-950/70 overflow-hidden">
                  <div className="px-4 py-4">
                    <AnswerMarkdown content={message.content} sources={message.sources || []} />
                    {message.retrieved_context && <div className="mt-3 text-[11px] text-slate-500">
                      Retrieved {message.retrieved_context.chunks_retrieved} context sources
                      {message.retrieved_context.repository_overview_used && <span> · repository overview</span>}
                      {message.retrieved_context.architecture_context_used && <span> · architecture analysis</span>}
                      {!message.retrieved_context.repository_overview_used && !message.retrieved_context.architecture_context_used && <span> · top similarity {Number(message.retrieved_context.top_similarity).toFixed(3)}</span>}
                      {!message.retrieved_context.context_sufficient && <span className="ml-1 text-amber-300">· insufficient context</span>}
                    </div>}
                    {message.sources?.length > 0 && <div className="mt-3 pt-3 border-t border-slate-800">
                      <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">Cited source files</p>
                      <div className="flex flex-wrap gap-2">
                        {message.sources.map((source) => <a key={source.citation_id} href={source.url || `https://github.com/${repoUrl.trim().replace(/^https?:\/\/(www\.)?github\.com\//i, '').replace(/\/$/, '')}/blob/HEAD/${source.path}#L${source.start_line}-L${source.end_line}`} target="_blank" rel="noreferrer"
                          className="inline-flex items-center gap-1.5 rounded-lg border border-cyan-900/70 bg-cyan-950/30 px-2.5 py-1.5 text-xs text-cyan-200 hover:border-cyan-600 hover:text-cyan-100">
                          <span className="font-semibold">[{source.citation_id}]</span><span className="font-mono">{source.path}:{source.start_line}-{source.end_line}</span><ExternalLink className="h-3 w-3" />
                        </a>)}
                      </div>
                    </div>}
                  </div>
                </article>
              ))}
            </div>}
          </div>}

        {(activePage === 'architecture' || architectureVisited) && <div className={activePage === 'architecture' ? 'rg-feature-surface' : 'hidden'}><Suspense fallback={<p role="status" className="rg-card p-5 text-xs text-slate-400">Loading architecture visualizer…</p>}>
          <ArchitectureVisualizer repoUrl={repoUrl} darkMode={theme === 'dark'} />
        </Suspense></div>}

        {(activePage === 'dependencies' || dependenciesVisited) && <div className={activePage === 'dependencies' ? 'rg-feature-surface' : 'hidden'}><Suspense fallback={<p role="status" className="rg-card p-5 text-xs text-slate-400">Loading dependency explorer…</p>}>
          <DependencyExplorer repoUrl={repoUrl} darkMode={theme === 'dark'} />
        </Suspense></div>}

        {/* Error Banner */}
        {activePage === 'home' && error && (
          <div className="mt-6 p-4 rounded-xl bg-rose-950/40 border border-rose-800/60 flex items-start gap-3 text-left">
            <AlertTriangle className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="text-sm font-semibold text-rose-300">Ingestion Failed</h4>
              <p className="text-xs text-rose-200/90 mt-1 leading-relaxed">{error}</p>
            </div>
          </div>
        )}

        {/* Loading Progress State */}
        {activePage === 'home' && loading && (
          <div className="mt-8 p-6 rounded-xl bg-slate-950/70 border border-slate-800/80 text-center space-y-3">
            <div className="flex items-center justify-center gap-3">
              <Loader2 className="h-6 w-6 text-cyan-400 animate-spin" />
              <span className="text-sm font-medium text-slate-200">
                Fetching repository tree and source files...
              </span>
            </div>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Connecting to GitHub REST API, filtering code by extension, and downloading source code files concurrently.
            </p>
          </div>
        )}
      </div>

      {/* Ingested Repository Dashboard */}
      {repoData && !loading && activePage === 'home' && (
        <details className="rg-feature-surface rg-card mt-4 overflow-hidden">
          <summary className="cursor-pointer px-5 py-4 text-sm font-semibold text-[#30285c]">Browse source files <span className="ml-2 text-xs font-normal text-[#77748f]">{repoData.files_returned} loaded of {repoData.total_source_files_found} found</span></summary>
          <div className="space-y-4 border-t border-[#e7e3f5] p-4">
          {/* Repository Meta Banner */}
          <div className="bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-2xl p-6 sm:p-8">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-slate-800/80">
              <div>
                <div className="flex items-center gap-3 flex-wrap">
                  <h3 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                    <span>{repoData.owner}</span>
                    <span className="text-slate-600">/</span>
                    <span className="text-cyan-400">{repoData.repository}</span>
                  </h3>
                  <a
                    href={`https://github.com/${repoData.owner}/${repoData.repository}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-cyan-300 px-2 py-1 rounded bg-slate-800/80 border border-slate-700/60 transition-colors"
                  >
                    <span>View on GitHub</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
                {repoData.description && (
                  <p className="text-xs sm:text-sm text-slate-300 mt-2 max-w-3xl leading-relaxed">
                    {repoData.description}
                  </p>
                )}
              </div>

              {/* Badges / Metrics */}
              <div className="flex items-center gap-2.5 flex-wrap">
                <div className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center gap-1.5 text-xs text-amber-300">
                  <Star className="h-3.5 w-3.5 fill-amber-400 text-amber-400" />
                  <span className="font-semibold">{formatStars(repoData.stars)}</span>
                </div>
                <div className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center gap-1.5 text-xs text-slate-300">
                  <GitBranch className="h-3.5 w-3.5 text-cyan-400" />
                  <span>{repoData.default_branch}</span>
                </div>
                <div className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center gap-1.5 text-xs text-slate-300">
                  <Files className="h-3.5 w-3.5 text-indigo-400" />
                  <span>{repoData.total_source_files_found} source files found</span>
                </div>
                <div className="px-3 py-1.5 rounded-xl bg-cyan-950/60 border border-cyan-800/60 flex items-center gap-1.5 text-xs text-cyan-300 font-semibold">
                  <FileCode className="h-3.5 w-3.5 text-cyan-400" />
                  <span>{repoData.files_returned} loaded for review</span>
                </div>
              </div>
            </div>

            {/* Truncation Notice */}
            {repoData.files_truncated && (
              <div className="mt-4 p-3.5 rounded-xl bg-amber-950/30 border border-amber-800/40 flex flex-wrap items-center gap-3 text-amber-300 text-xs">
                <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                <span className="min-w-0 flex-1">{repoData.truncation_reason}</span>
                <button type="button" onClick={() => handleIngest()} disabled={loading} className="shrink-0 rounded-lg border border-violet-300 bg-white px-3 py-1.5 font-semibold text-violet-700 hover:bg-violet-50 disabled:opacity-50">
                  {loading ? 'Refreshing…' : 'Refresh source files'}
                </button>
              </div>
            )}

            {/* Language Distribution Filter Pills */}
            <div className="mt-6 flex items-center gap-2 flex-wrap">
              <span className="text-xs text-slate-400 flex items-center gap-1 mr-1">
                <Filter className="h-3.5 w-3.5" /> Filter Language:
              </span>
              <button
                type="button"
                onClick={() => setSelectedLanguage('ALL')}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer border ${
                  selectedLanguage === 'ALL'
                    ? 'bg-cyan-500 text-slate-950 font-bold border-cyan-400'
                    : 'bg-slate-950 text-slate-400 hover:text-white border-slate-800'
                }`}
              >
                All ({repoData.files.length})
              </button>
              {Object.entries(languageStats).map(([lang, count]) => (
                <button
                  key={lang}
                  type="button"
                  onClick={() => setSelectedLanguage(lang)}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors cursor-pointer border ${
                    selectedLanguage === lang
                      ? 'bg-cyan-500 text-slate-950 font-bold border-cyan-400'
                      : 'bg-slate-950 text-slate-400 hover:text-white border-slate-800'
                  }`}
                >
                  {lang} ({count})
                </button>
              ))}
            </div>
          </div>

          {/* File Explorer & Code Viewer Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left: File List Panel */}
            <div className="lg:col-span-5 bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-2xl overflow-hidden flex flex-col h-[560px]">
              {/* Search Bar */}
              <div className="p-3.5 border-b border-slate-800 bg-slate-950/50">
                <div className="relative">
                  <Search className="h-3.5 w-3.5 text-slate-500 absolute inset-y-0 left-3 my-auto pointer-events-none" />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search files by path..."
                    className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-900 border border-slate-800 focus:border-cyan-500 rounded-lg text-slate-200 placeholder-slate-500 outline-none"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery('')}
                      className="absolute inset-y-0 right-2 flex items-center text-slate-500 hover:text-slate-300"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </div>
              </div>

              {/* Scrollable File List */}
              <div className="flex-1 overflow-y-auto divide-y divide-slate-800/40 p-2 space-y-1">
                {filteredFiles.length === 0 ? (
                  <div className="p-8 text-center text-xs text-slate-500">
                    No files match your search query.
                  </div>
                ) : (
                  filteredFiles.map((file) => {
                    const isSelected = activeFile?.path === file.path;
                    return (
                      <button
                        key={file.path}
                        type="button"
                        onClick={() => setActiveFile(file)}
                        className={`w-full text-left p-2.5 rounded-xl transition-all cursor-pointer flex items-center justify-between gap-2 text-xs ${
                          isSelected
                            ? 'bg-cyan-950/40 border border-cyan-500/40 text-cyan-200'
                            : 'hover:bg-slate-800/60 text-slate-300 border border-transparent'
                        }`}
                      >
                        <div className="flex items-center gap-2 truncate">
                          <Code2
                            className={`h-4 w-4 shrink-0 ${
                              isSelected ? 'text-cyan-400' : 'text-slate-500'
                            }`}
                          />
                          <span className="font-mono truncate">{file.path}</span>
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-medium border ${getLanguageColor(
                              file.language
                            )}`}
                          >
                            {file.language}
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {formatBytes(file.size)}
                          </span>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>

              {/* Footer status in file list */}
              <div className="px-4 py-2.5 bg-slate-950/70 border-t border-slate-800 text-[11px] text-slate-500 flex justify-between items-center">
                <span>Showing {filteredFiles.length} of {repoData.files.length} files</span>
                <span className="font-mono">Max 100 KB/file</span>
              </div>
            </div>

            {/* Right: Code Viewer Panel */}
            <div className="lg:col-span-7 bg-slate-900/90 backdrop-blur-md border border-slate-800 rounded-2xl overflow-hidden flex flex-col h-[560px]">
              {activeFile ? (
                <>
                  {/* File Header */}
                  <div className="p-3.5 border-b border-slate-800 bg-slate-950/80 flex items-center justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-2 truncate">
                      <Code2 className="h-4 w-4 text-cyan-400 shrink-0" />
                      <span className="text-xs font-mono font-semibold text-slate-200 truncate">
                        {activeFile.path}
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-medium border ${getLanguageColor(
                          activeFile.language
                        )}`}
                      >
                        {activeFile.language}
                      </span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {formatBytes(activeFile.size)}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={handleCopyCode}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-medium transition-colors cursor-pointer"
                    >
                      {copiedCode ? (
                        <>
                          <Check className="h-3.5 w-3.5 text-emerald-400" />
                          <span className="text-emerald-400">Copied!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="h-3.5 w-3.5" />
                          <span>Copy Content</span>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Code Viewer Body */}
                  <div className="flex-1 p-4 bg-slate-950 overflow-auto font-mono text-xs leading-relaxed text-slate-200">
                    <pre className="whitespace-pre">
                      <code>{activeFile.content}</code>
                    </pre>
                  </div>
                </>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500">
                  <Code2 className="h-10 w-10 text-slate-700 mb-3" />
                  <p className="text-sm font-medium text-slate-400">Select a file to inspect its source code</p>
                  <p className="text-xs text-slate-600 mt-1">
                    Click any file from the explorer on the left to preview its content.
                  </p>
                </div>
              )}
            </div>
          </div>
          </div>
        </details>
      )}
        </main>
      </div>
    </div>
  );
}

