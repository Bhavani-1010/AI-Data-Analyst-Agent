import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import './App.css'

// In local dev this falls back to your local Flask server. In production,
// Vercel will inject VITE_API_BASE (set in the Vercel dashboard) pointing at
// your deployed Render backend URL.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:5000'
const STORAGE_KEY = 'ai_data_analyst_chats'

function timeNow() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function makeWelcomeMessage() {
  return {
    role: 'agent',
    text: "Ask me anything about your Sales data — totals, trends, correlations, ask me to plot a chart, or ask for a downloadable report.",
    chartUrl: null,
    reportUrl: null,
    time: timeNow(),
  }
}

function makeNewChat() {
  return {
    id: crypto.randomUUID(),
    title: 'New query',
    messages: [makeWelcomeMessage()],
    createdAt: Date.now(),
  }
}

function loadChatsFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed) && parsed.length > 0) return parsed
    return null
  } catch {
    return null
  }
}

function tagForMessage(msg) {
  if (msg.role === 'user') return null
  if (msg.isError) return 'ERROR'
  if (msg.chartUrl) return 'CHART'
  if (msg.reportUrl) return 'REPORT'
  return 'ANSWER'
}

function App() {
  const [chats, setChats] = useState(() => loadChatsFromStorage() || [makeNewChat()])
  const [activeChatId, setActiveChatId] = useState(() => chats[0].id)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const activeChat = chats.find((c) => c.id === activeChatId) || chats[0]

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(chats))
  }, [chats])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeChat?.messages])

  function updateActiveChatMessages(updater) {
    setChats((prev) =>
      prev.map((chat) =>
        chat.id === activeChatId ? { ...chat, messages: updater(chat.messages) } : chat
      )
    )
  }

  function setActiveChatTitle(title) {
    setChats((prev) =>
      prev.map((chat) => (chat.id === activeChatId ? { ...chat, title } : chat))
    )
  }

  function handleNewChat() {
    const newChat = makeNewChat()
    setChats((prev) => [newChat, ...prev])
    setActiveChatId(newChat.id)
    setInput('')
  }

  function handleSelectChat(id) {
    setActiveChatId(id)
    setInput('')
  }

  async function handleSend() {
    const question = input.trim()
    if (!question || loading) return

    if (activeChat.messages.length <= 1) {
      setActiveChatTitle(question.length > 42 ? question.slice(0, 42) + '…' : question)
    }

    updateActiveChatMessages((msgs) => [
      ...msgs,
      { role: 'user', text: question, chartUrl: null, time: timeNow() },
    ])
    setInput('')
    setLoading(true)

    try {
      const response = await fetch(`${API_BASE}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || 'Something went wrong.')
      }

      updateActiveChatMessages((msgs) => [
        ...msgs,
        {
          role: 'agent',
          text: data.answer,
          chartUrl: data.chart_url ? `${API_BASE}${data.chart_url}` : null,
          reportUrl: data.report_url ? `${API_BASE}${data.report_url}` : null,
          time: timeNow(),
        },
      ])
    } catch (err) {
      updateActiveChatMessages((msgs) => [
        ...msgs,
        { role: 'agent', text: `Error: ${err.message}`, chartUrl: null, isError: true, time: timeNow() },
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-label">Query Log</div>
        <button className="new-chat-btn" onClick={handleNewChat}>
          + New query
        </button>
        <div className="chat-list">
          {chats
            .slice()
            .sort((a, b) => b.createdAt - a.createdAt)
            .map((chat) => (
              <button
                key={chat.id}
                className={`chat-list-item ${chat.id === activeChatId ? 'active' : ''}`}
                onClick={() => handleSelectChat(chat.id)}
              >
                <span className="chat-list-item-marker">›</span>
                {chat.title}
              </button>
            ))}
        </div>
      </aside>

      <div className="app">
        <header className="app-header">
          <div className="app-header-titles">
            <h1>AI Data Analyst Agent</h1>
            <p>Natural-language querying over Superstore sales data</p>
          </div>
          <div className="status-readout">
            <span className="status-dot" />
            sales.db · 51,290 rows
          </div>
        </header>

        <div className="chat-window">
          {activeChat.messages.map((msg, i) => {
            const tag = tagForMessage(msg)
            return (
              <div key={i} className={`message ${msg.role} ${msg.isError ? 'error' : ''}`}>
                <div className="message-inner">
                  {tag && <div className={`eyebrow eyebrow-${tag.toLowerCase()}`}>{tag}</div>}
                  <div className="message-bubble">
                    <ReactMarkdown>{msg.text}</ReactMarkdown>
                    {msg.chartUrl && (
                      <img src={msg.chartUrl} alt="Generated chart" className="chart-image" />
                    )}
                    {msg.reportUrl && (
                      <a className="download-report-btn" href={msg.reportUrl} download>
                        ⬇ Download report (.xlsx)
                      </a>
                    )}
                  </div>
                  {msg.time && <div className="message-time">{msg.time}</div>}
                </div>
              </div>
            )
          })}

          {loading && (
            <div className="message agent">
              <div className="message-inner">
                <div className="eyebrow eyebrow-working">WORKING</div>
                <div className="message-bubble loading-bubble">
                  <span className="dot" />
                  <span className="dot" />
                  <span className="dot" />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <div className="input-bar">
          <span className="input-prompt">›</span>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about your sales data..."
            rows={1}
            disabled={loading}
          />
          <button onClick={handleSend} disabled={loading || !input.trim()}>
            Run
          </button>
        </div>
      </div>
    </div>
  )
}

export default App
