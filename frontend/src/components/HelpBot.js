import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, X, Send, Bot, User, ChevronRight, RotateCcw } from 'lucide-react';

const KNOWLEDGE_BASE = [
  {
    keywords: ['what', 'hitl', 'human-in-the-loop', 'gateway', 'about'],
    answer: `The **HITL Gateway** is enterprise middleware that sits between AI agents and high-risk actions. When an AI agent detects a threat or needs to perform a critical action, it **pauses** and sends a request to the gateway. A human reviewer then approves, rejects, or escalates the action before the agent proceeds.\n\nThis ensures AI never acts autonomously on high-risk decisions.`,
  },
  {
    keywords: ['azure', 'durable', 'functions', 'architecture', 'how', 'work'],
    answer: `The gateway runs on **Azure Durable Functions**, which provides:\n\n- **HTTP Trigger** — Receives HITL requests from agents\n- **Durable Orchestrator** — Manages the lifecycle by racing an SLA timer against a human decision event\n- **Durable Timer** — Auto-escalates if no human responds within the SLA\n- **External Event** — Waits for the human decision with zero compute cost\n\nThis means the agent is **truly suspended** (not polling) and Azure charges nothing while waiting.`,
  },
  {
    keywords: ['sla', 'timeout', 'urgency', 'escalat'],
    answer: `Each request has an **urgency level** with a corresponding SLA timeout:\n\n| Urgency | SLA Timeout |\n|---------|------------|\n| CRITICAL | 5 minutes |\n| HIGH | 15 minutes |\n| NORMAL | 60 minutes |\n| LOW | 24 hours |\n\nIf no human responds within the SLA, the system **auto-escalates** to a senior reviewer or Slack channel, and the agent receives a safe-default action.`,
  },
  {
    keywords: ['demo', 'try', 'test', 'trigger', 'scenario'],
    answer: `To try a live demo:\n\n1. Go to the **Live Demo** page from the sidebar\n2. Click any **threat scenario** card (e.g., Lateral Movement)\n3. Watch the **Azure pipeline animate** in real-time\n4. When it reaches "Human Review", click **Approve** or **Reject**\n5. See the agent receive the callback and execute the action\n\nYou can also check the **Pending Inbox** for requests waiting for review, and the **Audit Trail** for the complete compliance log.`,
  },
  {
    keywords: ['security', 'auth', 'safe', 'protect'],
    answer: `The gateway implements multiple security layers:\n\n- **API Key Authentication** — All agent requests must include a valid key\n- **HMAC Signatures** — Webhook payloads are cryptographically signed\n- **SSRF Protection** — Callback URLs are validated against allowlists\n- **Rate Limiting** — Per-agent request throttling\n- **Replay Prevention** — Nonce + timestamp validation\n- **Input Sanitization** — XSS and injection prevention on all inputs`,
  },
  {
    keywords: ['agent', 'integrate', 'connect', 'api', 'endpoint'],
    answer: `Any AI agent can integrate by sending a POST to \`/api/hitl_ingress\` with:\n\n\`\`\`json\n{\n  "agent_id": "your-agent-id",\n  "action_description": "What the agent wants to do",\n  "urgency": "CRITICAL",\n  "callback_url": "https://your-agent/resume",\n  "required_role": "SecOps_Lead",\n  "context": { "any": "metadata" }\n}\n\`\`\`\n\nThe agent then **blocks** until a human decision is made and the callback is delivered.`,
  },
  {
    keywords: ['team', 'microsoft', 'notification', 'slack', 'channel'],
    answer: `When a request arrives, the gateway sends notifications via:\n\n- **Microsoft Teams** — Adaptive Cards to the relevant channel\n- **Slack** — Rich message with approve/reject buttons\n- **Web Dashboard** — Real-time pending inbox (what you're looking at now)\n\nReviewers can approve/reject from any channel. The first response wins.`,
  },
  {
    keywords: ['compliance', 'audit', 'log', 'trace'],
    answer: `Every state transition is logged for full compliance:\n\n- Request received (PENDING)\n- Timer started (SLA deadline)\n- Decision received (APPROVED/REJECTED/ESCALATED)\n- Callback delivered (COMPLETE)\n\nAll events flow to **Azure Application Insights** for querying:\n\`\`\`kql\ntraces | where message contains "[AUDIT]" | order by timestamp\n\`\`\`\n\nCheck the **Audit Trail** page for a visual timeline.`,
  },
];

const QUICK_ACTIONS = [
  { label: 'What is HITL?', query: 'What is the HITL Gateway?' },
  { label: 'How does Azure work here?', query: 'How do Azure Durable Functions work?' },
  { label: 'Show me a demo', query: 'How do I try the demo?' },
  { label: 'SLA & Urgency', query: 'What are the SLA timeouts?' },
];

function findAnswer(query) {
  const lower = query.toLowerCase();
  let bestMatch = null;
  let bestScore = 0;

  for (const entry of KNOWLEDGE_BASE) {
    const score = entry.keywords.reduce((acc, kw) => acc + (lower.includes(kw) ? 1 : 0), 0);
    if (score > bestScore) {
      bestScore = score;
      bestMatch = entry;
    }
  }

  if (bestScore > 0) return bestMatch.answer;

  return `I can help you understand the HITL Gateway! Try asking about:\n\n- What is the HITL Gateway?\n- How does Azure Durable Functions work?\n- How do I try the live demo?\n- What are the SLA timeouts?\n- How does security work?\n- How do agents integrate?`;
}

function formatMessage(text) {
  // Basic markdown-like formatting
  return text
    .split('\n')
    .map((line, i) => {
      // Bold
      line = line.replace(/\*\*(.*?)\*\*/g, '<strong class="text-hitl-text-primary">$1</strong>');
      // Inline code
      line = line.replace(/`([^`]+)`/g, '<code class="bg-hitl-muted/20 px-1 rounded text-xs font-mono text-blue-300">$1</code>');
      // Table headers
      if (line.includes('|') && line.includes('---')) return null;
      if (line.startsWith('|')) {
        const cells = line.split('|').filter(Boolean).map(c => c.trim());
        return `<div class="flex gap-4 text-xs"><span class="w-20 text-hitl-muted">${cells[0]}</span><span>${cells[1] || ''}</span></div>`;
      }
      // List items
      if (line.startsWith('- ')) {
        return `<div class="flex gap-2"><span class="text-hitl-muted">•</span><span>${line.slice(2)}</span></div>`;
      }
      // Numbered list
      if (/^\d+\./.test(line)) {
        return `<div class="flex gap-2"><span class="text-hitl-active">${line.match(/^\d+/)[0]}.</span><span>${line.replace(/^\d+\.\s*/, '')}</span></div>`;
      }
      if (line.trim() === '') return '<div class="h-2"></div>';
      return `<div>${line}</div>`;
    })
    .filter(Boolean)
    .join('');
}

const INITIAL_MESSAGE = {
  role: 'bot',
  text: "Hi! I'm the HITL Gateway assistant. I can help you understand how this system works, guide you through the demo, or answer questions about the architecture.\n\nWhat would you like to know?",
};

export default function HelpBot() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([INITIAL_MESSAGE]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const handleSend = async (text) => {
    const query = text || input.trim();
    if (!query) return;

    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: query }]);
    setIsTyping(true);

    // Simulate typing delay
    await new Promise(r => setTimeout(r, 600 + Math.random() * 800));

    const answer = findAnswer(query);
    setMessages(prev => [...prev, { role: 'bot', text: answer }]);
    setIsTyping(false);
  };

  const handleNewChat = () => {
    setMessages([INITIAL_MESSAGE]);
    setInput('');
    setIsTyping(false);
  };

  const handleEndChat = () => {
    setMessages([INITIAL_MESSAGE]);
    setInput('');
    setIsTyping(false);
    setIsOpen(false);
  };

  return (
    <>
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-4 right-4 md:bottom-6 md:right-6 z-50 w-12 h-12 md:w-14 md:h-14 rounded-full flex items-center justify-center shadow-lg transition-all duration-300 ${
          isOpen
            ? 'bg-hitl-muted/20 border border-hitl-border text-hitl-text-primary'
            : 'bg-hitl-active hover:bg-blue-500 text-white'
        }`}
        data-testid="helpbot-toggle"
      >
        {isOpen ? <X size={20} /> : <MessageCircle size={20} />}
      </button>

      {/* Chat Panel */}
      {isOpen && (
        <div
          className="fixed bottom-20 md:bottom-24 right-2 md:right-6 z-50 w-[calc(100vw-1rem)] sm:w-[380px] max-h-[70vh] sm:max-h-[520px] bg-hitl-surface border border-hitl-border rounded-xl shadow-2xl flex flex-col overflow-hidden"
          data-testid="helpbot-panel"
        >
          {/* Header */}
          <div className="bg-gradient-to-r from-hitl-active to-blue-700 px-4 py-3 flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
              <Bot size={18} className="text-white" />
            </div>
            <div className="flex-1">
              <div className="text-sm font-semibold text-white">HITL Assistant</div>
              <div className="text-[10px] text-white/70">Powered by Azure AI</div>
            </div>
            {messages.length > 1 && (
              <button
                onClick={handleNewChat}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] bg-white/10 hover:bg-white/20 border border-white/20 rounded-lg text-white transition-colors"
                title="Start a new conversation"
              >
                <RotateCcw size={12} />
                <span>New Chat</span>
              </button>
            )}
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 md:p-4 space-y-4 min-h-[200px] max-h-[50vh] sm:min-h-[280px] sm:max-h-[340px]">
            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'bot' && (
                  <div className="w-6 h-6 rounded-full bg-hitl-active/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <Bot size={12} className="text-hitl-active" />
                  </div>
                )}
                <div
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-hitl-active text-white'
                      : 'bg-hitl-muted/10 text-hitl-secondary'
                  }`}
                  dangerouslySetInnerHTML={
                    msg.role === 'bot' ? { __html: formatMessage(msg.text) } : undefined
                  }
                >
                  {msg.role === 'user' ? msg.text : undefined}
                </div>
                {msg.role === 'user' && (
                  <div className="w-6 h-6 rounded-full bg-hitl-muted/20 flex items-center justify-center flex-shrink-0 mt-1">
                    <User size={12} className="text-hitl-text-primary" />
                  </div>
                )}
              </div>
            ))}
            {isTyping && (
              <div className="flex gap-2">
                <div className="w-6 h-6 rounded-full bg-hitl-active/20 flex items-center justify-center flex-shrink-0">
                  <Bot size={12} className="text-hitl-active" />
                </div>
                <div className="bg-hitl-muted/10 rounded-lg px-3 py-2">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-hitl-muted rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-hitl-muted rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-hitl-muted rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Quick Actions */}
          {messages.length <= 2 && (
            <div className="px-4 pb-2 flex flex-wrap gap-1.5">
              {QUICK_ACTIONS.map((qa) => (
                <button
                  key={qa.label}
                  onClick={() => handleSend(qa.query)}
                  className="flex items-center gap-1 px-2.5 py-1 text-[10px] bg-hitl-muted/10 border border-hitl-border rounded-full text-hitl-secondary hover:text-hitl-text-primary hover:border-hitl-text-primary/30 transition-colors"
                >
                  {qa.label} <ChevronRight size={10} />
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div className="border-t border-hitl-border p-3">
            {messages.length > 1 && (
              <div className="flex gap-2 mb-2">
                <button
                  onClick={handleEndChat}
                  className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-[10px] bg-red-500/20 hover:bg-red-500/30 border border-red-500/30 rounded-lg text-red-400 hover:text-red-300 transition-colors"
                >
                  <X size={12} />
                  <span>End Chat & Close</span>
                </button>
              </div>
            )}
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Ask about the HITL Gateway..."
                className="flex-1 bg-hitl-input border border-hitl-border rounded-lg px-3 py-2 text-xs text-hitl-text-primary placeholder:text-hitl-muted focus:outline-none focus:border-hitl-active focus:ring-1 focus:ring-hitl-active/30"
                data-testid="helpbot-input"
              />
              <button
                onClick={() => handleSend()}
                className="px-3 py-2 bg-hitl-active hover:bg-blue-500 rounded-lg transition-colors"
                data-testid="helpbot-send"
              >
                <Send size={14} className="text-white" />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
