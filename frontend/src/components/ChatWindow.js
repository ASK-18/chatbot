import React, { useState, useRef, useEffect } from 'react';
import { Bot, X, Send, Loader2 } from 'lucide-react';
import '../Chatbot.css';

// ✅ ADD THIS: generate unique session ID
const generateSessionId = () => crypto.randomUUID();

const ChatWindow = ({ setIsOpen }) => {
  const [messages, setMessages] = useState([
    { role: 'bot', content: 'Hello! I have analyzed your PDF. How can I help?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  // ✅ ADD THIS: persistent session ID for conversation memory
  const sessionIdRef = useRef(generateSessionId());

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input;

    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionIdRef.current // ✅ REQUIRED
        }),
      });

      const data = await response.json();

      setMessages(prev => [
        ...prev,
        { role: 'bot', content: data.answer }
      ]);
    } catch (error) {
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
            <div style={{ fontWeight: '600', fontSize: '15px' }}>
              AI Assistant
            </div>
            <div style={{ fontSize: '10px', opacity: 0.8 }}>
              PDF ANALYST
            </div>
          </div>
        </div>
        <X size={20} onClick={() => setIsOpen(false)} style={{ cursor: 'pointer' }} />
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`msg-bubble msg-${msg.role}`}>
            {msg.content}
          </div>
        ))}

        {loading && (
          <div
            className="msg-bubble msg-bot italic"
            style={{ display: 'flex', gap: '8px', alignItems: 'center' }}
          >
            <Loader2 size={14} className="animate-spin" /> Thinking...
          </div>
        )}

        <div ref={scrollRef} />
      </div>

      <div className="chat-input-area">
        <div className="input-box">
          <input
            placeholder="Ask a question..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
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
