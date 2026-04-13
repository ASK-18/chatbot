import React, { useState, useEffect, useCallback } from 'react';
import {
  MessageCircle,
  X,
  Clock,
  FileText,
  Search,
  Brain,
  ChevronRight,
  Sparkles
} from 'lucide-react';

import ChatWindow from './components/ChatWindow';
import './Chatbot.css';

function App() {
  const [isOpen, setIsOpen] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [chatKey, setChatKey] = useState(0);

  // ---------------- Fetch past sessions ----------------
  useEffect(() => {
    if (!isOpen) return;

    fetch('http://localhost:8000/sessions')
      .then(res => res.json())
      .then(data => setSessions(data.sessions || []))
      .catch(() => setSessions([]));
  }, [isOpen]);

  // ---------------- Stable callback ----------------
  const handleSessionCreated = useCallback((id) => {
    setActiveSessionId(id);
  }, []);

  // ---------------- Resume session ----------------
  const handleResumeSession = (id) => {
    setActiveSessionId(id);
    setChatKey(prev => prev + 1);
    setShowHistory(false);
    setIsOpen(true);
  };

  // ---------------- New chat ----------------
  const handleNewChat = () => {
    setActiveSessionId(null);
    setChatKey(prev => prev + 1);
    setIsOpen(true);
  };

  // ---------------- Time helper ----------------
  const formatTime = (isoString) => {
  if (!isoString) return '';

  // ✅ Fix: backend `/sessions` returns timezone‑naive timestamps
  // If no timezone info is present, assume UTC and append 'Z'
  const normalized = isoString.endsWith('Z')
    ? isoString
    : `${isoString}Z`;

  const messageDate = new Date(normalized); // correctly parsed as UTC → local
  const now = new Date();

  let diffMs = now.getTime() - messageDate.getTime();

  // Safety guard for small clock skews
  if (diffMs < 0) diffMs = 0;

  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHrs = Math.floor(diffMins / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;

  const diffDays = Math.floor(diffHrs / 24);
  return `${diffDays}d ago`;
};
console.log(
  'Session timestamps:',
  sessions.map(s => ({
    raw: s.last_timestamp,
    parsed: new Date(s.last_timestamp).toString()
  }))
);

  return (
    <div className="app-root">
      {/* ---------------- Hero Section ---------------- */}
      <div className="hero-section">
        <div className="hero-glow"></div>
        <div className="hero-content">
          <div className="hero-badge">
            <Sparkles size={14} />
            <span>AI-Powered RAG Chatbot</span>
          </div>

          <h1 className="hero-title">
            Insurance <span className="gradient-text">Document Assistant</span>
          </h1>

          <p className="hero-subtitle">
            Ask questions about your insurance policy and get instant, accurate
            answers powered by AI retrieval and conversational memory.
          </p>

          <button className="hero-cta" onClick={handleNewChat}>
            <MessageCircle size={18} />
            Start a Conversation
          </button>
        </div>
      </div>

      {/* ---------------- How It Works ---------------- */}
      <div className="how-it-works">
        <h2 className="section-title">How It Works</h2>
        <p className="section-subtitle">
          Our RAG pipeline answers your questions in three intelligent steps
        </p>

        <div className="steps-grid">
          <div className="step-card">
            <div className="step-icon step-icon-1">
              <FileText size={24} />
            </div>
            <div className="step-number">01</div>
            <h3>Document Analysis</h3>
            <p>
              Your PDF is split into meaningful chunks and embedded into a vector
              database for fast semantic search.
            </p>
          </div>

          <div className="step-card">
            <div className="step-icon step-icon-2">
              <Search size={24} />
            </div>
            <div className="step-number">02</div>
            <h3>Smart Retrieval</h3>
            <p>
              Relevant chunks are retrieved and reranked using a cross-encoder to
              maximize relevance.
            </p>
          </div>

          <div className="step-card">
            <div className="step-icon step-icon-3">
              <Brain size={24} />
            </div>
            <div className="step-number">03</div>
            <h3>Conversational Memory</h3>
            <p>
              Each conversation is stored in MongoDB, allowing natural follow-ups
              without repeating context.
            </p>
          </div>
        </div>
      </div>

      {/* ---------------- Conversation History ---------------- */}
      {sessions.length > 0 && (
        <div className="history-section">
          <div className="history-header">
            <h2 className="section-title">Recent Conversations</h2>
            <button
              className="view-all-btn"
              onClick={() => setShowHistory(!showHistory)}
            >
              {showHistory ? 'Show Less' : 'View All'}
              <ChevronRight size={16} className={showHistory ? 'rotate-90' : ''} />
            </button>
          </div>

          <div className="sessions-grid">
            {(showHistory ? sessions : sessions.slice(0, 3)).map(s => (
              <div
                key={s.session_id}
                className="session-card"
                onClick={() => handleResumeSession(s.session_id)}
              >
                <div className="session-card-top">
                  <div className="session-icon">
                    <MessageCircle size={16} />
                  </div>
                  <span className="session-time">
                    <Clock size={12} />
                    {formatTime(s.last_timestamp)}
                  </span>
                </div>

                <p className="session-preview">
                  {s.preview || 'Empty conversation'}
                </p>

                <div className="session-meta">
                  <span>{s.message_count} messages</span>
                  <span className="resume-link">Resume →</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ---------------- Chat Widget ---------------- */}
      <div className="chat-container">
        {isOpen && (
          <ChatWindow
            key={chatKey}
            setIsOpen={setIsOpen}
            sessionId={activeSessionId}
            onSessionCreated={handleSessionCreated}
          />
        )}

        <button
          className="toggle-button"
          onClick={() => {
            if (isOpen) setIsOpen(false);
            else handleNewChat();
          }}
        >
          {isOpen ? <X size={28} /> : <MessageCircle size={28} />}
        </button>
      </div>
    </div>
  );
}

export default App;
