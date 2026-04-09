import React, { useState } from 'react';
import { MessageCircle, X } from 'lucide-react';
import ChatWindow from './components/ChatWindow';
import './Chatbot.css'; 

function App() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#e2e8f0' }}>
      <div style={{ padding: '40px' }}>
        <h1>My RAG Application</h1>
        <p>The PDF chatbot is ready in the corner.</p>
      </div>

      <div className="chat-container">
        {isOpen && <ChatWindow setIsOpen={setIsOpen} />}
        
        <button className="toggle-button" onClick={() => setIsOpen(!isOpen)}>
          {isOpen ? <X size={32} /> : <MessageCircle size={32} />}
        </button>
      </div>
    </div>
  );
}

export default App;
