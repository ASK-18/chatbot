import React, { useState, useRef, useEffect } from 'react';
import { Bot, X, Send, Loader2, History } from 'lucide-react';
import '../Chatbot.css';

const generateSessionId = () => crypto.randomUUID();

const ChatWindow = ({ setIsOpen, sessionId, onSessionCreated }) => {
  const [messages, setMessages] = useState([
    { role: 'bot', content: 'Hello! I have analyzed your PDF. How can I help?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const scrollRef = useRef(null);
  const sessionIdRef = useRef(null);

  // ✅ Capture session origin ONCE (StrictMode safe)
  const initialSessionIdRef = useRef(sessionId);
  const isResumedRef = useRef(false);

  // ---------------- Initialize session ----------------
  useEffect(() => {
    if (initialSessionIdRef.current) {
      sessionIdRef.current = initialSessionIdRef.current;
      isResumedRef.current = true;
    } else {
      sessionIdRef.current = generateSessionId();
      isResumedRef.current = false;
      onSessionCreated?.(sessionIdRef.current);
    }

    setMessages([
      { role: 'bot', content: 'Hello! I have analyzed your PDF. How can I help?' }
    ]);
    setHistoryLoaded(false);
  }, [onSessionCreated]);

  // ---------------- Load history ----------------
  useEffect(() => {
    if (isResumedRef.current && !historyLoaded) {
      fetch(`http://localhost:8000/history/${sessionIdRef.current}`)
        .then(res => res.json())
        .then(data => {
          if (data.messages?.length) {
            const loaded = data.messages.map(m => ({
              role: m.role === 'user' ? 'user' : 'bot',
              content: m.content
            }));
            setMessages(prev => [prev[0], ...loaded]);
          }
          setHistoryLoaded(true);
        })
        .catch(() => setHistoryLoaded(true));
    }
  }, [historyLoaded]);

  // ---------------- Auto scroll ----------------
  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ---------------- Send message ----------------
  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionIdRef.current
        })
      });

      const data = await res.json();
      setMessages(prev => [...prev, { role: 'bot', content: data.answer }]);
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'bot', content: 'Backend error. Is the server running?' }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-window">
      <div className="chat-header">
        <div className="bot-info">
          <div className="icon-circle">
            <Bot size={22} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 15 }}>
              AI Assistant
            </div>
            <div className="session-label">
              {isResumedRef.current ? (
                <>
              <History size={8} />
                RESUMED SESSION
              </>
              ) : (
              <>
              <span style={{ fontSize: '10px' }}>✨</span>
                NEW SESSION
              </>
              )}
          </div>
          </div>
        </div>

        <X size={20} onClick={() => setIsOpen(false)} style={{ cursor: 'pointer' }} />
      </div>

      <div className="chat-messages">
        {messages.map((m, i) => (
          <div key={i} className={`msg-bubble msg-${m.role}`}>
            {m.content}
          </div>
        ))}

        {loading && (
          <div className="msg-bubble msg-bot">
            <Loader2 size={14} className="spin-icon" /> Thinking...
          </div>
        )}

        <div ref={scrollRef} />
      </div>

      <div className="chat-input-area">
        <div className="input-box">
          <input
            placeholder="Ask a question..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSend()}
          />
          <button className="send-button" onClick={handleSend}>
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatWindow;
