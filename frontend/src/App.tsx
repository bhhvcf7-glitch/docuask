import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import {
  ArrowLeft, ArrowRight, BookOpenText, CheckCircle2, CircleAlert,
  FileSearch, FileText, Languages, LoaderCircle, LogOut, MessageSquareText,
  Send, ShieldCheck, Sparkles, Square, UploadCloud,
} from 'lucide-react'
import { api, authorizedFetch, streamAnswer, type Citation, type DocumentItem } from './api'

import { endSession, setSession, type TokenPair } from './session'
import { PdfViewer } from './PdfViewer'

type Lang = 'ar' | 'en'
type User = { id: string; email: string }
type Session = TokenPair

const copy = {
  ar: {
    subtitle: 'اسأل مستنداتك. واحصل على إجابات بمصادرها.',
    login: 'تسجيل الدخول', register: 'حساب جديد', email: 'البريد الإلكتروني',
    password: 'كلمة المرور', start: 'متابعة', logout: 'تسجيل الخروج',
    welcome: 'مستنداتك، أوضح من أي وقت.', welcomeDesc: 'ارفع ملف PDF، واسأل بالعربي أو الإنجليزي. كل إجابة مرتبطة بصفحتها الأصلية.',
    yourFiles: 'مستنداتك', upload: 'ارفع ملف PDF', drop: 'اختر ملف PDF من جهازك',
    fileHelp: 'PDF نصي فقط · حتى 10 ميجابايت', uploading: 'جارٍ الرفع...',
    empty: 'ما عندك مستندات إلى الآن', emptyHelp: 'ابدأ برفع ملف PDF نصي.',
    ready: 'جاهز', queued: 'في الانتظار', processing: 'قيد المعالجة', failed: 'فشل',
    askTitle: 'اسأل مستنداتك', askHelp: 'أسئلتك تُبحث داخل مستنداتك فقط.',
    placeholder: 'مثال: ما أهم نتائج التقرير؟', ask: 'اسأل',
    thinking: 'جارٍ البحث والإجابة...', stop: 'إيقاف', sources: 'المصادر',
    page: 'صفحة', prompt: 'ارفع مستندًا جاهزًا ثم اكتب سؤالك للبدء.',
    cited: 'المصادر مرتبطة بالمقاطع المسترجعة، لكنها لا تضمن صحة كل جملة.',
    note: 'الملفات تخص حسابك فقط. لا ترفع بيانات شديدة الحساسية في هذه النسخة التجريبية.',
    error: 'حدث خطأ', tryAgain: 'حاول مرة ثانية', signedIn: 'الحساب',
  },
  en: {
    subtitle: 'Ask your documents. Get answers with sources.',
    login: 'Sign in', register: 'Create account', email: 'Email address',
    password: 'Password', start: 'Continue', logout: 'Sign out',
    welcome: 'Your documents, explained.', welcomeDesc: 'Upload a PDF and ask in Arabic or English. Answers link back to their source pages.',
    yourFiles: 'Your documents', upload: 'Upload a PDF', drop: 'Choose a PDF from your device',
    fileHelp: 'Text-based PDF only · up to 10 MB', uploading: 'Uploading...',
    empty: 'No documents yet', emptyHelp: 'Start by uploading a text-based PDF.',
    ready: 'Ready', queued: 'Queued', processing: 'Processing', failed: 'Failed',
    askTitle: 'Ask your documents', askHelp: 'Questions are answered from your documents only.',
    placeholder: 'For example: What are the key findings?', ask: 'Ask',
    thinking: 'Searching and answering...', stop: 'Stop', sources: 'Sources',
    page: 'Page', prompt: 'Upload a ready document, then ask a question.',
    cited: 'Citations link to retrieved excerpts, but cannot guarantee every claim is correct.',
    note: 'Files are scoped to your account. Avoid highly sensitive documents in this development MVP.',
    error: 'Something went wrong', tryAgain: 'Try again', signedIn: 'Account',
  },
}

function formatSize(size: number): string {
  return size < 1024 * 1024 ? `${Math.ceil(size / 1024)} KB` : `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export default function App() {
  const [lang, setLang] = useState<Lang>('ar')
  const t = copy[lang]
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [viewer, setViewer] = useState<Citation>()
  const [history, setHistory] = useState<{id: string; created_at: string}[]>([])
  const [turns, setTurns] = useState<{question: string; answer: string}[]>([])
  const [conversationId, setConversationId] = useState<string | undefined>()
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [citations, setCitations] = useState<Citation[]>([])
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [asking, setAsking] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const loadDocuments = useCallback(async (key: string) => {
    const list = await api<DocumentItem[]>('/documents', key)
    setDocuments(list)
  }, [])

  useEffect(() => {
    if (!token) return
    void loadDocuments(token).catch(() => undefined)
    const poll = window.setInterval(() => {
      void loadDocuments(token).catch(() => undefined)
    }, 4000)
    return () => window.clearInterval(poll)
  }, [token, loadDocuments])

  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'
  }, [lang])

  useEffect(() => () => abortRef.current?.abort(), [])

  async function authenticate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      if (authMode === 'register') {
        await api<User>('/auth/register', null, {
          method: 'POST', body: JSON.stringify({ email, password }),
        })
      }
      const session = await api<Session>('/auth/login', null, {
        method: 'POST', body: JSON.stringify({ email, password }),
      })
      const profile = await api<User>('/auth/me', session.access_token)
      setSession(session)
      setUser(profile)
      setToken(session.access_token)
      setPassword('')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t.error)
    } finally {
      setBusy(false)
    }
  }

  async function upload(file: File | undefined) {
    if (!file || !token) return
    setUploading(true)
    setError('')
    try {
      const form = new FormData()
      form.append('file', file)
      await api<DocumentItem>('/documents', token, { method: 'POST', body: form })
      await loadDocuments(token)
      if (fileRef.current) fileRef.current.value = ''
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t.error)
    } finally {
      setUploading(false)
    }
  }

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const prompt = question.trim()
    if (!prompt || !token || asking) return
    setError('')
    setAnswer('')
    setCitations([])
    setAsking(true)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      let chat = conversationId
      if (!chat) {
        const created = await api<{ id: string }>('/conversations', token, { method: 'POST' })
        chat = created.id
        setConversationId(chat)
      }
      await streamAnswer(token, prompt, controller.signal, (message) => {
        if (message.type === 'token') {
          setAnswer(old => old + message.payload.text)
        } else if (message.type === 'citations') {
          setCitations(message.payload.sources)
        } else if (message.type === 'refusal') {
          setAnswer(message.payload.answer)
        } else if (message.type === 'error') {
          setError(message.payload.message)
        }
      }, chat)
    } catch (cause) {
      if (!controller.signal.aborted) {
        setError(cause instanceof Error ? cause.message : t.error)
      }
    } finally {
      setAsking(false)
      abortRef.current = null
    }
  }

  function signOut() {
    endSession()
    abortRef.current?.abort()
    setConversationId(undefined)
    setViewer(undefined)
    setHistory([])
    setTurns([])
    setToken(null)
    setUser(null)
    setDocuments([])
    setAnswer('')
    setCitations([])
    setQuestion('')
  }

  async function refreshHistory() {
    if (token) setHistory(await api<typeof history>('/conversations', token))
  }

  async function openHistory(id: string) {
    if (!token || asking) return
    try {
      const chat = await api<{turns: typeof turns}>('/conversations/' + id, token)
      setConversationId(id)
      setTurns(chat.turns)
      setAnswer('')
      setCitations([])
      setViewer(undefined)
    } catch (cause) { setError(String(cause)) }
  }

  async function removeHistory(id: string) {
    if (!token || asking) return
    try {
      const response = await authorizedFetch('/conversations/' + id, token, { method: 'DELETE' })
      if (!response.ok) throw new Error('HTTP ' + response.status)
      if (conversationId === id) { setConversationId(undefined); setTurns([]); setAnswer(''); setCitations([]); setViewer(undefined) }
      await refreshHistory()
    } catch (cause) { setError(String(cause)) }
  }

  const hasReady = documents.some(doc => doc.status === 'ready')
  const otherLang = lang === 'ar' ? 'English' : 'العربية'

  return (
    <div className="site">
      <header className="topbar">
        <div className="logo" aria-label="DocuAsk">
          <div className="logo-icon"><BookOpenText size={23} strokeWidth={2.2} /></div>
          <div className="logo-name">Docu<span>Ask</span><small>{t.subtitle}</small></div>
        </div>
        <div className="top-actions">
          <button className="lang-button" type="button" onClick={() => setLang(lang === 'ar' ? 'en' : 'ar')}>
            <Languages size={18} /><span>{otherLang}</span>
          </button>
          {token && (
            <button type="button" className="signout" onClick={signOut}>
              <LogOut size={17} /><span>{t.logout}</span>
            </button>
          )}
        </div>
      </header>

      {!token ? (
        <main className="welcome-layout">
          <section className="welcome-panel">
            <div className="eyebrow"><Sparkles size={15} /> DOCUASK MVP</div>
            <h1>{t.welcome}</h1>
            <p>{t.welcomeDesc}</p>
            <div className="benefits">
              <span><FileSearch size={19} /> PDF</span>
              <span><Languages size={19} /> عربي + English</span>
              <span><ShieldCheck size={19} /> Citations</span>
            </div>
            <div className="welcome-decoration" aria-hidden="true">
              <div className="deco-sheet"><div /><div /><div /><div /></div>
              <div className="deco-quote"><span>“</span><div /><div /><div /></div>
            </div>
          </section>
          <section className="login-card" aria-label={t.login}>
            <div className="auth-switch">
              <button type="button" className={authMode === 'login' ? 'active' : ''} onClick={() => { setAuthMode('login'); setError('') }}>{t.login}</button>
              <button type="button" className={authMode === 'register' ? 'active' : ''} onClick={() => { setAuthMode('register'); setError('') }}>{t.register}</button>
            </div>
            <h2>{authMode === 'login' ? t.login : t.register}</h2>
            <form onSubmit={authenticate} className="form-stack">
              <label>{t.email}
                <input type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} required placeholder="name@example.com" dir="ltr" />
              </label>
              <label>{t.password}
                <input type="password" autoComplete={authMode === 'login' ? 'current-password' : 'new-password'} minLength={authMode === 'register' ? 12 : undefined} value={password} onChange={e => setPassword(e.target.value)} required placeholder="••••••••••••" dir="ltr" />
              </label>
              {error && <p className="form-error" role="alert"><CircleAlert size={16} />{error}</p>}
              <button type="submit" className="primary" disabled={busy}>
                {busy ? <LoaderCircle className="spin" size={18} /> : lang === 'ar' ? <ArrowLeft size={18} /> : <ArrowRight size={18} />}
                {t.start}
              </button>
            </form>
            <p className="privacy-note"><ShieldCheck size={17} />{t.note}</p>
          </section>
        </main>
      ) : (
        <main className="workspace">
          <aside className="sidebar">
            <div className="section-heading"><div><span className="eyebrow muted">{t.signedIn}</span><strong className="user-email" dir="ltr">{user?.email}</strong></div></div>
            <div className="sidebar-heading"><h2>{t.yourFiles}</h2><span className="count">{documents.length}</span></div>
            <div className="upload-panel">
              <input
                ref={fileRef} type="file" accept=".pdf,application/pdf" id="pdf-upload"
                onChange={event => void upload(event.currentTarget.files?.[0])}
                disabled={uploading}
              />
              <label htmlFor="pdf-upload" className={'upload-target' + (uploading ? ' disabled' : '')}>
                {uploading ? <LoaderCircle className="spin" size={30} /> : <UploadCloud size={30} />}
                <strong>{uploading ? t.uploading : t.drop}</strong>
                <small>{t.fileHelp}</small>
              </label>
            </div>
            <div className="document-list" aria-live="polite">
              {documents.length === 0 && (
                <div className="empty-docs"><FileText size={30} /><p>{t.empty}</p><small>{t.emptyHelp}</small></div>
              )}
              {documents.map(doc => (
                <div className="document" key={doc.id}>
                  <div className="document-icon"><FileText size={21} /></div>
                  <div className="document-meta">
                    <strong title={doc.original_name}>{doc.original_name}</strong>
                    <div className="file-meta"><span>{formatSize(doc.size_bytes)}</span><span className={'status ' + doc.status}>
                      {doc.status === 'ready' ? <CheckCircle2 size={12} /> : doc.status === 'failed' ? <CircleAlert size={12} /> : <LoaderCircle size={12} />}
                      {t[doc.status]}
                    </span></div>
                  </div>
                </div>
              ))}
            </div>
            <p className="sidebar-footer">{t.note}</p>
          </aside>

          <section className="chat-panel">
            <div className="chat-heading">
              <div className="chat-icon"><MessageSquareText size={22} /></div>
              <div><h1>{t.askTitle}</h1><p>{t.askHelp}</p></div>
              <button type="button" disabled={asking} onClick={() => { setConversationId(undefined); setTurns([]); setViewer(undefined); setAnswer(''); setCitations([]); setQuestion(''); setError('') }}>{lang === 'ar' ? 'محادثة جديدة' : 'New chat'}</button>
            </div>
            <div className="chat-body">
              <button disabled={asking} onClick={() => void refreshHistory().catch(cause => setError(String(cause)))}>{lang === "ar" ? "عرض المحادثات السابقة" : "Show previous chats"}</button>
              {history.map(chat => <div key={chat.id}><button disabled={asking} onClick={() => void openHistory(chat.id)}>{new Date(chat.created_at).toLocaleString()}</button><button disabled={asking} onClick={() => void removeHistory(chat.id)}>{lang === "ar" ? "حذف" : "Delete"}</button></div>)}
              {turns.map((turn, i) => <article key={i}><strong dir="auto">{turn.question}</strong><p dir="auto">{turn.answer}</p></article>)}
              {viewer && token && <PdfViewer key={viewer.chunk_id} source={viewer} token={token} lang={lang} close={() => setViewer(undefined)}/>}
              {!answer && !asking && !error ? (
                <div className="empty-answer">
                  <div className="empty-answer-icon"><Sparkles size={34} /></div>
                  <h2>{t.welcome}</h2>
                  <p>{hasReady ? t.askHelp : t.prompt}</p>
                </div>
              ) : (
                <div className="answer-area">
                  <div className="answer-label"><Sparkles size={17} /><span>DocuAsk</span></div>
                  {answer && <p className="answer-text" dir="auto">{answer}</p>}
                  {asking && <div className="loading-line"><LoaderCircle className="spin" size={15} />{t.thinking}</div>}
                  {error && <p className="form-error" role="alert"><CircleAlert size={16} />{error}</p>}
                  {citations.length > 0 && (
                    <div className="sources">
                      <h3><BookOpenText size={17} />{t.sources}</h3>
                      <div className="sources-grid">{citations.map(source => (
                        <article className="source" key={source.chunk_id}>
                          <span className="source-number">{source.number}</span>
                          <div className="source-content">
                            <strong>{source.filename}</strong>
                            <button type="button" className="source-page" onClick={() => setViewer(source)}>{t.page} {source.page_number} · {lang === "ar" ? "فتح المصدر" : "Open source"}</button>
                            <p dir="auto">{source.text}</p>
                          </div>
                        </article>
                      ))}</div>
                      <p className="source-disclaimer">{t.cited}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="composer-wrap">
              <form className="composer" onSubmit={ask}>
                <textarea
                  rows={2}
                  value={question}
                  onChange={event => setQuestion(event.target.value)}
                  placeholder={t.placeholder}
                  aria-label={t.askTitle}
                  maxLength={2000}
                  onKeyDown={event => {
                    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                      event.preventDefault()
                      event.currentTarget.form?.requestSubmit()
                    }
                  }}
                />
                {asking ? (
                  <button className="send-button stop-button" type="button" onClick={() => abortRef.current?.abort()} aria-label={t.stop}><Square size={18} fill="currentColor" /></button>
                ) : (
                  <button className="send-button" type="submit" disabled={!question.trim() || !hasReady} aria-label={t.ask}><Send size={19} /></button>
                )}
              </form>
              <p className="composer-caption">{t.cited}</p>
            </div>
          </section>
        </main>
      )}
    </div>
  )
}
