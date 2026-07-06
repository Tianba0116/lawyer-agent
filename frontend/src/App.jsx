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
  const [selectedDoc, setSelectedDoc] = useState(null)  // 当前选中的目标文档
  const [query, setQuery] = useState('')
  const [messages, setMessages] = useState([])
  const [streaming, setStreaming] = useState('')
  const [toolCalls, setToolCalls] = useState([])         // 当前对话的真实工具调用记录
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [editModal, setEditModal] = useState(null)
  const [editForm, setEditForm] = useState({ name: '', icon: '', model: '', type: 'openai', api_key_env: '', base_url: '' })
  const [docPreview, setDocPreview] = useState(null)     // 文档预览弹窗: {name, content, loading}
  const [docViewer, setDocViewer] = useState(null)       // 双栏详情页: {name, pdf_type, chunks, size} | null
  const [viewerContent, setViewerContent] = useState('') // OCR / 提取的文字
  const [viewerPages, setViewerPages] = useState(0)       // PDF 总页数
  const [viewerLoading, setViewerLoading] = useState(false)
  const chatRef = useRef(null)
  const abortRef = useRef(null)

  const cur = providers.find(p => p.id === activeProvider) || DEFAULT_PROVIDER

  useEffect(() => { chatRef.current?.scrollTo(0, chatRef.current.scrollHeight) }, [messages, streaming])
  useEffect(() => { fetchProviders(); fetchDocuments() }, [])
  // 当文档列表变化时，如果没选中任何文档且有文档存在，自动选中第一个
  useEffect(() => {
    if (!selectedDoc && documents.length > 0) setSelectedDoc(documents[0])
    if (selectedDoc && !documents.find(d => d.name === selectedDoc.name)) {
      setSelectedDoc(documents.length > 0 ? documents[0] : null)
    }
  }, [documents])

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
      if (res.ok) {
        const data = await res.json()
        await fetchDocuments()
        // 扫描件提示 OCR 处理完成
        if (data.pdf_type === 'scanned') {
          setError('')  // 清除之前的错误
        }
      } else setError('上传失败，请重试。')
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
    setToolCalls([])
    setLoading(true)
    setMessages(m => [...m, { role: 'user', text: q }])

    const file_name = selectedDoc?.name || ''
    const controller = new AbortController()
    abortRef.current = controller
    const localToolCalls = []
    try {
      const res = await fetch(`${API}/api/query/stream`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, file_name, provider: activeProvider }),
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
          try {
            const data = JSON.parse(line.slice(6))
            if (data.token) { fullText += data.token; setStreaming(fullText) }
            else if (data.tool_start) { localToolCalls.push({ name: data.tool_start, status: 'running' }); setToolCalls([...localToolCalls]) }
            else if (data.tool_end) { const last = localToolCalls.find(t => t.status === 'running'); if (last) last.status = 'done'; setToolCalls([...localToolCalls]) }
          } catch {}
        }
      }
      setMessages(m => [...m, { role: 'ai', text: fullText, toolCalls: [...localToolCalls], searchedDoc: file_name || null }])
      setStreaming('')
    } catch (err) {
      if (err.name !== 'AbortError') setMessages(m => [...m, { role: 'ai', text: `请求失败：${err.message || ''}` }])
      setStreaming('')
    }
    setToolCalls([])
    setLoading(false)
    abortRef.current = null
  }

  const handlePreviewDoc = async (doc) => {
    setDocPreview({ name: doc.name, content: '', loading: true })
    try {
      const res = await fetch(`${API}/api/documents/${encodeURIComponent(doc.name)}/content`)
      if (res.ok) {
        const data = await res.json()
        setDocPreview({ name: doc.name, content: data.content || '(无内容)', loading: false, pdf_type: data.pdf_type })
      } else {
        setDocPreview({ name: doc.name, content: '无法加载文档内容', loading: false })
      }
    } catch {
      setDocPreview({ name: doc.name, content: '网络请求失败', loading: false })
    }
  }

  const openDocViewer = async (doc) => {
    setDocViewer(doc)
    setViewerLoading(true)
    setViewerContent('')
    setViewerPages(0)
    try {
      const res = await fetch(`${API}/api/documents/${encodeURIComponent(doc.name)}/content`)
      if (res.ok) {
        const data = await res.json()
        setViewerContent(data.content || '(无内容)')
        setViewerPages(data.pages || 0)
      } else {
        setViewerContent('无法加载文档内容')
      }
    } catch {
      setViewerContent('网络请求失败')
    }
    setViewerLoading(false)
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
              {documents.slice(0, 5).map(d => <div key={d.name} className="kb-mini-item" title={d.name}>{d.pdf_type === 'scanned' ? '🖼️' : '📄'} {d.name}</div>)}
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
      {view === 'knowledge' && !docViewer && (
        <main className="main">
          <div className="knowledge-view">
            <div className="kv-header"><h2>知识库管理</h2><p>管理已上传的法律文档，AI 助手将基于这些文档进行检索增强回答</p></div>
            <div className="upload-row">
              <label className="upload-row-btn">＋ 上传文档<input type="file" accept=".pdf" onChange={handleUpload} hidden /></label>
              <span className="upload-row-hint">支持 PDF 格式 · 已上传 {documents.length} 份{documents.length > 0 && <span className="pdf-type-badge scanned" style={{marginLeft:4}}>{documents.filter(d=>d.pdf_type==='scanned').length}份扫描件</span>}</span>
              {uploading && <span className="upload-row-status">正在处理...</span>}
            </div>
            {uploading && <div className="uploading-bar">正在上传并索引文档...</div>}
            <div className="doc-list">
              {documents.length === 0 && !uploading && <div className="empty-kb"><span>📂</span><p>知识库为空，请上传法律文档</p></div>}
              {documents.map(doc => (
                <div key={doc.name} className="doc-card" onClick={() => openDocViewer(doc)} style={{cursor:'pointer'}}>
                  <span className="doc-card-icon">{doc.pdf_type === 'scanned' ? '🖼️' : '📄'}</span>
                  <div className="doc-card-info">
                    <div className="doc-card-name">
                      {doc.name}
                      {doc.pdf_type === 'scanned' && <span className="pdf-type-badge scanned">扫描件</span>}
                      {doc.pdf_type === 'text' && <span className="pdf-type-badge text">文本型</span>}
                    </div>
                    <div className="doc-card-meta">{doc.chunks} 块 · {(doc.size / 1024).toFixed(1)} KB{doc.uploaded_at && ` · ${new Date(doc.uploaded_at).toLocaleDateString('zh-CN')}`}{' — 点击查看详情'}</div>
                  </div>
                  <button className="doc-card-del" onClick={(e) => { e.stopPropagation(); handleDelete(doc.name) }}>删除</button>
                </div>
              ))}
            </div>
          </div>
        </main>
      )}

      {/* ---- Doc Viewer (two-panel detail) ---- */}
      {docViewer && (
        <main className="main">
          <div className="doc-viewer">
            <div className="viewer-topbar">
              <button className="viewer-back" onClick={() => { setDocViewer(null); setViewerContent('') }}>← 返回知识库</button>
              <span className="viewer-title">{docViewer.name}</span>
              {docViewer.pdf_type === 'scanned' && <span className="pdf-type-badge scanned">扫描件</span>}
              {docViewer.pdf_type === 'text' && <span className="pdf-type-badge text">文本型</span>}
              <span className="viewer-meta">{docViewer.chunks} 块 · {(docViewer.size / 1024).toFixed(1)} KB</span>
            </div>
            <div className="viewer-panels">
              <div className="viewer-left">
                {viewerLoading && !viewerPages ? (
                  <div className="viewer-left-loading"><div className="typing-dots"><span></span><span></span><span></span></div></div>
                ) : viewerPages > 0 ? (
                  Array.from({ length: viewerPages }, (_, i) => (
                    <img key={i} src={`${API}/api/documents/${encodeURIComponent(docViewer.name)}/pages/${i + 1}`} loading="lazy" alt={`Page ${i + 1}`} />
                  ))
                ) : (
                  <div className="viewer-left-loading">无法加载 PDF 页面</div>
                )}
              </div>
              <div className="viewer-right">
                {viewerLoading ? (
                  <div className="viewer-right-loading"><div className="typing-dots"><span></span><span></span><span></span></div></div>
                ) : (
                  <div className="markdown-body"><ReactMarkdown remarkPlugins={[remarkGfm]}>{viewerContent}</ReactMarkdown></div>
                )}
              </div>
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
                            {/* Real tool execution timeline from SSE events */}
                            {m.toolCalls && m.toolCalls.length > 0 && (
                              <div className="tool-timeline">
                                {m.toolCalls.map((t, ti) => (
                                  <div key={ti} className="tool-item">
                                    <span className="tool-check">{t.status === 'done' ? '✓' : '⟳'}</span>
                                    {t.name === 'search_legal_document' ? '检索知识库文档' : t.name === 'summarize_document' ? '生成文档摘要' : t.name === 'generate_report_tool' ? '生成报告' : t.name}
                                  </div>
                                ))}
                              </div>
                            )}
                            <div className="markdown-body">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                            </div>
                            {/* Real source tags: show the actually searched document */}
                            {m.searchedDoc && (
                              <div className="source-tags">
                                <span className="source-tag">📎 {m.searchedDoc}</span>
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
                {documents.length > 0 && (
                  <div className="doc-selector">
                    <span className="doc-selector-label">📋 检索目标：</span>
                    <select className="doc-select" value={selectedDoc?.name || ''} onChange={e => { const d = documents.find(x => x.name === e.target.value); if (d) setSelectedDoc(d) }}>
                      {documents.map(d => (
                        <option key={d.name} value={d.name}>{d.pdf_type === 'scanned' ? '🖼️' : '📄'} {d.name}</option>
                      ))}
                    </select>
                    {selectedDoc?.pdf_type === 'scanned' && <span className="pdf-type-badge scanned" style={{marginLeft:6}}>扫描件</span>}
                    {selectedDoc?.pdf_type === 'text' && <span className="pdf-type-badge text" style={{marginLeft:6}}>文本型</span>}
                  </div>
                )}
                <div className="input-row">
                  <textarea className="query-input" value={query} onChange={e => { setQuery(e.target.value); setError('') }} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleQuery() } }} placeholder={documents.length > 0 ? `基于「${selectedDoc?.name || ''}」提问，Enter 发送` : '请先上传文档，Enter 发送'} rows={1} />
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
                        <span className="dot" style={{background: d.pdf_type === 'scanned' ? 'var(--warning)' : 'var(--success)'}}></span>
                        <span style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={d.name}>{d.name}</span>
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

      {/* ---- Doc Preview Modal ---- */}
      {docPreview && (
        <div className="modal-overlay" onClick={() => setDocPreview(null)}>
          <div className="modal doc-preview-modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>📄 {docPreview.name}</h3>
              {docPreview.pdf_type && (
                <span className={`pdf-type-badge ${docPreview.pdf_type}`} style={{marginLeft:8}}>
                  {docPreview.pdf_type === 'scanned' ? '扫描件 · OCR提取' : '文本型'}
                </span>
              )}
              <button className="modal-close" onClick={() => setDocPreview(null)}>✕</button>
            </div>
            <div className="modal-body doc-preview-body">
              {docPreview.loading ? (
                <div className="typing-dots"><span></span><span></span><span></span></div>
              ) : (
                <div className="markdown-body doc-preview-content">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{docPreview.content}</ReactMarkdown>
                </div>
              )}
            </div>
          </div>
        </div>
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
