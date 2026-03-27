import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader, MessageCircle } from 'lucide-react';

const ChatTab = () => {
  const [messages, setMessages] = useState([
    { role: 'ai', text: 'FinSight AI is ready. Ask me any details about your statement, trends, or specific transactions.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('http://127.0.0.1:8000/api/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg })
      });
      const data = await res.json();
      setMessages(prev => [...prev, { role: 'ai', text: data.response || "I couldn't generate an answer." }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', text: 'Error connecting to the intelligence engine.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="tab-content-wrapper fade-in chat-page-wrapper">
      <div className="immersive-chat-card">
        <div className="chat-header-large">
          <div className="chat-avatar">
            <Bot size={28} color="white" />
          </div>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.5rem' }}>Talk to your Statement</h2>
            <p style={{ margin: 0, opacity: 0.8, fontSize: '0.85rem' }}>Ask natural language questions about your business health</p>
          </div>
        </div>

        <div className="chat-messages-viewport" ref={scrollRef}>
          {messages.map((m, i) => (
            <div key={i} className={`chat-line ${m.role}`}>
              <div className="chat-avatar-mini">
                {m.role === 'ai' ? <Bot size={14} /> : <User size={14} />}
              </div>
              <div className="chat-bubble-main">
                {m.text}
              </div>
            </div>
          ))}
          {loading && (
            <div className="chat-line ai">
              <div className="chat-avatar-mini anim-pulse">
                <Bot size={14} />
              </div>
              <div className="chat-bubble-main loading-dots">
                <Loader size={12} className="spin" /> Thinking...
              </div>
            </div>
          )}
        </div>

        <div className="chat-input-row">
          <input 
            type="text" 
            placeholder="Search your data (e.g. 'How much did I spend on Software in total?')" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          />
          <button onClick={handleSend} disabled={!input.trim() || loading}>
            <Send size={18} />
            <span>Send Query</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ChatTab;
