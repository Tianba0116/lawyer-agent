import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API = 'http://localhost:8000'

const SUGGESTIONS = [
  '合同中违约责任条款如何认定？',
  '请分析证据链的完整性与证明力',
  '该案适用哪些法律条款？',
  '请对起诉书进行法律审查',
]

const DEFAULT_PROVIDER = { id: 'deepseek', name: 'DeepSeek', icon: '🪷', model: 'deepseek-chat', type: 'deepseek', api_key_env: 'DEEPSEEK_API_KEY', base_url: '', builtin: true }

const TYPE_LABELS = { deepseek: 'DeepSeek SDK', openai: 'OpenAI 兼容 API' }

function App() {
  const [view, setView] = useState('chat')
  const [providers, setProviders] = useState([DEFAULT_PROVIDER])
  const [activeProvider, setActiveProvider] = useState('deepseek')
  const [documents, setDocuments] = useState([])
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [editModal, setEditModal] = useState(null)
  const [editForm, setEditForm] = useState({ name: '', icon: '', model: '', type: 'openai', api_key_env: '', base_url: '' })
  const chatRef = useRef(null)
  const abortRef = useRef(null)

  const cur = providers.find(p => p.id === activeProvider) || DEFAULT_PROVIDER

  useEffect(() => { chatRef.current?.scrollTo(0, chatRef.current.scrollHeight) }, [messages, streaming])
  useEffect(() => { fetchProviders(); fetchDocuments() }, [])

  const fetchProviders = async () => {
    try {
      const res = await fetch(`${API}/api/providers`)
      const data = await res.json()
      setProviders(data.providers || [DEFAULT_PROVIDER])
      setActiveProvider(data.active || 'deepseek')
    } catch {}
  }

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API}/api/documents`)
      const data = await res.json()
      setDocuments(data.documents || [])
    } catch {}
  }

  const handleActivate = async (id) => {
    await fetch(`${API}/api/providers/${id}/activate`, { method: 'PUT' })
    setActiveProvider(id)
  }

  const openEdit = (p) => {
    setEditModal(p ? p.id : 'new')
    setEditForm(p ? { name: p.name, icon: p.icon, model: p.model, type: p.type, api_key_env: p.api_key_env, base_url: p.base_url || '' }
      : { name: '', icon: '', model: '', type: 'openai', api_key_env: '', base_url: '' })
  }

  const saveEdit = async () => {
    if (!editForm.name || !editForm.model) return
    const body = { ...editForm }
    try {
      if (editModal === 'new') {
        await fetch(`${API}/api/providers`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      } else {
        await fetch(`${API}/api/providers/${editModal}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
      }
      await fetchProviders()
      setEditModal(null)
    } catch { alert('保存失败') }
  }

  const handleDeleteProvider = async (id) => {
    await fetch(`${API}/api/providers/${id}`, { method: 'DELETE' })
    await fetchProviders()
  }

  const handleUpload = async (e) => {
    const f = e.target.files[0]
    if (!f) return
    setUploading(true)
    setError('')
    const fd = new FormData()
    fd.append('file', f)
    try {
      const res = await fetch(`${API}/api/upload`, { method: 'POST', body: fd })
      if (res.ok) await fetchDocuments()
      else setError('上传失败，请重试。')
    } catch { setError('无法连接后端服务。') }
    setUploading(false)
  }

  const handleDelete = async (name) => {
    await fetch(`${API}/api/documents/${encodeURIComponent(name)}`, { method: 'DELETE' })
    await fetchDocuments()
  }

  const handleQuery = async (text) => {
    const q = text || query
    if (!q.trim() || loading) return
    setError('')
    setQuery('')
    setStreaming('')
    setLoading(true)
    setMessages(m => [...m, { role: 'user', text: q }])

    const controller = new AbortController()
    abortRef.current = controller
    try {
      const res = await fetch(`${API}/api/query/stream`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, file_name: '', provider: activeProvider }),
        signal: controller.signal,
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = '', fullText = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try { const data = JSON.parse(line.slice(6)); if (data.token) { fullText += data.token; setStreaming(fullText) } } catch {}
        }
      }
      setMessages(m => [...m, { role: 'ai', text: fullText }])
      setStreaming('')
    } catch (err) {
      if (err.name !== 'AbortError') setMessages(m => [...m, { role: 'ai', text: `请求失败：${err.message || ''}` }])
      setStreaming('')
    }
    setLoading(false)
    abortRef.current = null
  }

  const handleCopy = (text) => { navigator.clipboard.writeText(text) }

  return (
    <div className="app">
      {/* ---- Sidebar ---- */}
      <aside className="sidebar">
        <div className="sidebar-inner">
          <div className="logo" onClick={() => { setView('chat'); setMessages([]) }}>
            <span className="logo-icon">&#9878;</span><span>AI 法律助手</span>
          </div>

          <nav className="nav">
            {[{ k: 'chat', i: '💬', l: '对话' }, { k: 'knowledge', i: '📚', l: '知识库' }, { k: 'model', i: '⚙️', l: '模型' }].map(({ k, i, l }) => (
              <button key={k} className={`nav-item ${view === k ? 'active' : ''}`} onClick={() => setView(k)}>
                <span className="nav-icon">{i}</span> {l}
                {k === 'knowledge' && documents.length > 0 && <span className="badge">{documents.length}</span>}
              </button>
            ))}
          </nav>

          {view !== 'knowledge' && documents.length > 0 && (
            <div className="kb-mini">
              <div className="kb-mini-title">知识库 · {documents.length} 份文档</div>
              {documents.slice(0, 5).map(d => <div key={d.name} className="kb-mini-item" title={d.name}>{d.name}</div>)}
            </div>
          )}

          {view === 'knowledge' && (
            <label className="upload-link">＋ 上传文档<input type="file" accept=".pdf" onChange={handleUpload} hidden /></label>
          )}
        </div>

        <div className="sidebar-footer">
          <div className="current-model" onClick={() => setView('model')}>
            <span>{cur.icon || '🤖'}</span><span>{cur.name}</span><span className="chevron">›</span>
          </div>
        </div>
      </aside>

      {/* ---- Model View ---- */}
      {view === 'model' && (
        <main className="main">
          <div className="model-view">
            <div className="mv-header">
              <h2>模型选择</h2>
              <p>选择或管理用于法律问答与文档分析的 AI 大模型</p>
            </div>
            <div className="model-list">
              {providers.map(p => (
                <div key={p.id} className={`model-card ${activeProvider === p.id ? 'selected' : ''}`} onClick={() => handleActivate(p.id)}>
                  <div className="model-card-left">
                    <span className="model-card-icon">{p.icon || '🤖'}</span>
                    <div className="model-card-info">
                      <div className="model-card-name">{p.name}</div>
                      <div className="model-card-model">{p.model}</div>
                      <div className="model-card-desc">模型：{p.model}{p.base_url ? ` · ${p.base_url}` : ''}</div>
                    </div>
                  </div>
                  <div className="model-card-actions" onClick={e => e.stopPropagation()}>
                    <button className="mca-btn" onClick={() => openEdit(p)} title="编辑">✏️</button>
                    {!p.builtin && <button className="mca-btn del" onClick={() => handleDeleteProvider(p.id)} title="删除">🗑️</button>}
                  </div>
                </div>
              ))}
              <button className="add-model-btn" onClick={() => openEdit(null)}>＋ 添加模型</button>
            </div>
          </div>
        </main>
      )}

      {/* ---- Knowledge View ---- */}
      {view === 'knowledge' && (
        <main className="main">
          <div className="knowledge-view">
            <div className="kv-header"><h2>知识库管理</h2><p>管理已上传的法律文档，AI 助手将基于这些文档进行检索增强回答</p></div>
            <label className="upload-card"><span className="upload-plus">＋</span><span>上传新文档</span><span className="upload-hint">支持 PDF 格式，可上传多份文档构建知识库</span><input type="file" accept=".pdf" onChange={handleUpload} hidden /></label>
            {uploading && <div className="uploading-bar">正在上传并索引文档...</div>}
            <div className="doc-list">
              {documents.length === 0 && !uploading && <div className="empty-kb"><span>📂</span><p>知识库为空，请上传法律文档</p></div>}
              {documents.map(doc => (
                <div key={doc.name} className="doc-card">
                  <span className="doc-card-icon">📄</span>
                  <div className="doc-card-info"><div className="doc-card-name">{doc.name}</div><div className="doc-card-meta">{doc.chunks} 块 · {(doc.size / 1024).toFixed(1)} KB{doc.uploaded_at && ` · ${new Date(doc.uploaded_at).toLocaleDateString('zh-CN')}`}</div></div>
                  <button className="doc-card-del" onClick={() => handleDelete(doc.name)}>删除</button>
                </div>
              ))}
            </div>
          </div>
        </main>
      )}

      {/* ---- Chat View ---- */}
      {view === 'chat' && (
        <main className="main">
          <div className="chat-layout">
            <div className="chat-center">
              <div className="chat" ref={chatRef}>
                {messages.length === 0 && !streaming && (
                  <div className="welcome">
                    <h1>检察院 AI 办案助手</h1>
                    <p className="welcome-sub">基于知识库检索增强的法律智能分析系统</p>
                    <div className="suggestions">{SUGGESTIONS.map((s, i) => <button key={i} className="sug-card" onClick={() => handleQuery(s)}>{s}</button>)}</div>
                  </div>
                )}
                {messages.map((m, i) => (
                  <div key={i} className={`msg-row ${m.role}`}>
                    <div className="msg-avatar">{m.role === 'user' ? '👤' : '⚖️'}</div>
                    <div className="msg-content">
                      <div className="msg-sender">{m.role === 'user' ? '承办人' : 'AI 办案助手'}</div>
                      <div className="msg-bubble">
                        {m.role === 'ai' ? (
                          <>
                            {/* Tool execution timeline — visual only, for Agent messages */}
                            {m.text && m.text.length > 0 && i > 0 && messages[i-1]?.role === 'user' && (
                              <div className="tool-timeline">
                                <div className="tool-item"><span className="tool-check">✓</span> 文档检索完成</div>
                                <div className="tool-item"><span className="tool-check">✓</span> 法律条款分析</div>
                              </div>
                            )}
                            <div className="markdown-body">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                            </div>
                            {documents.length > 0 && (
                              <div className="source-tags">
                                {documents.slice(0, 3).map(d => <span key={d.name} className="source-tag">📎 {d.name}</span>)}
                              </div>
                            )}
                          </>
                        ) : <div className="msg-text">{m.text}</div>}
                      </div>
                      {m.role === 'ai' && <button className="copy-link" onClick={() => handleCopy(m.text)}>复制</button>}
                    </div>
                  </div>
                ))}
                {streaming && (
                  <div className="msg-row ai">
                    <div className="msg-avatar">⚖️</div><div className="msg-content"><div className="msg-sender">AI 办案助手</div><div className="msg-bubble"><div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm]}>{streaming}</ReactMarkdown></div><span className="cursor-blink">|</span></div></div>
                  </div>
                )}
                {loading && !streaming && (
                  <div className="msg-row ai"><div className="msg-avatar">⚖️</div><div className="msg-content"><div className="msg-sender">AI 办案助手</div><div className="msg-bubble"><div className="typing-dots"><span></span><span></span><span></span></div></div></div></div>
                )}
              </div>
              <div className="input-area">
                <div className="input-row">
                  <textarea className="query-input" value={query} onChange={e => { setQuery(e.target.value); setError('') }} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleQuery() } }} placeholder="输入案件相关问题，Enter 发送，Shift+Enter 换行" rows={1} />
                  <button className="send-btn" onClick={() => handleQuery()} disabled={loading || !query.trim()}>发送</button>
                </div>
                {error && <div className="error-msg">{error}</div>}
              </div>
            </div>

            {/* Right Context Panel */}
            <aside className="context-panel">
              <div className="cp-section">
                <div className="cp-section-title">📋 知识库</div>
                <div className="cp-card">
                  {documents.length === 0 ? (
                    <div style={{fontSize:12,color:'var(--text-caption)'}}>暂无文档，请上传法律文档构建知识库</div>
                  ) : (
                    documents.slice(0, 8).map(d => (
                      <div key={d.name} className="cp-card-row">
                        <span className="dot"></span>
                        <span style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{d.name}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
              <div className="cp-section">
                <div className="cp-section-title">⚙️ 当前模型</div>
                <div className="cp-card">
                  <div style={{fontSize:13,fontWeight:600}}>{cur.icon} {cur.name}</div>
                  <div className="cp-stat">{cur.model}</div>
                </div>
              </div>
              {messages.length > 0 && (
                <div className="cp-section">
                  <div className="cp-section-title">💬 对话统计</div>
                  <div className="cp-card">
                    <div className="cp-card-row"><span>消息数</span><span style={{marginLeft:'auto',fontWeight:600}}>{messages.length}</span></div>
                    <div className="cp-card-row"><span>状态</span><span style={{marginLeft:'auto',color:'var(--success)',fontWeight:600}}>进行中</span></div>
                  </div>
                </div>
              )}
            </aside>
          </div>
        </main>
      )}

      {/* ---- Edit Modal ---- */}
      {editModal && (
        <div className="modal-overlay" onClick={() => setEditModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>{editModal === 'new' ? '添加模型' : '编辑模型'}</h3>
              <button className="modal-close" onClick={() => setEditModal(null)}>✕</button>
            </div>
            <div className="modal-body">
              <label className="field"><span>名称</span><input value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} placeholder="如：豆包大模型" /></label>
              <label className="field"><span>图标</span><input value={editForm.icon} onChange={e => setEditForm({ ...editForm, icon: e.target.value })} placeholder="如：🫘" /></label>
              <label className="field"><span>模型</span><input value={editForm.model} onChange={e => setEditForm({ ...editForm, model: e.target.value })} placeholder="如：doubao-pro-32k" /></label>
              <label className="field"><span>类型</span>
                <select value={editForm.type} onChange={e => setEditForm({ ...editForm, type: e.target.value })}>
                  <option value="deepseek">DeepSeek SDK</option>
                  <option value="openai">OpenAI 兼容 API</option>
                </select>
              </label>
              <label className="field"><span>API Key 环境变量</span><input value={editForm.api_key_env} onChange={e => setEditForm({ ...editForm, api_key_env: e.target.value })} placeholder="如：DOUBAO_API_KEY" /></label>
              {editForm.type === 'openai' && <label className="field"><span>API 端点</span><input value={editForm.base_url} onChange={e => setEditForm({ ...editForm, base_url: e.target.value })} placeholder="如：https://ark.cn-beijing.volces.com/api/v3" /></label>}
            </div>
            <div className="modal-footer">
              <button className="btn-cancel" onClick={() => setEditModal(null)}>取消</button>
              <button className="btn-save" onClick={saveEdit}>保存</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
