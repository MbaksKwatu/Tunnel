'use client';

import { useState, useRef, useEffect } from 'react';
import AppLayout from '@/components/Layout/AppLayout';
import DynamicDashboard from '@/components/DynamicDashboard';
import { initialDashboardSchema } from '@/lib/dashboardSchema';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import axios from 'axios';
import { motion } from 'framer-motion';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

export default function EvaluatePage() {
  const [dashboard, setDashboard] = useState(initialDashboardSchema);
  const [messages, setMessages] = useState<Message[]>([
    { role: 'assistant', content: "Hello! I'm Parity. I can help you analyze this company's financial data. Ask me to drill down into revenue, profitability, or create a forecast." }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const suggestions = [
    "Explain Q2 revenue drop",
    "Drill into profitability", 
    "Forecast next 12 months",
    "Show expense breakdown"
  ];

  const handleSend = async (text = input) => {
    if (!text.trim() || isLoading) return;

    const userMessage = text;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      // Call backend to mutate dashboard based on instruction
      const response = await axios.post('http://localhost:8000/mutate-dashboard', {
        dashboard: dashboard,
        instruction: userMessage
      });

      const newDashboard = response.data.dashboard;
      const aiMessage = response.data.message || "I've updated the dashboard based on your request.";
      
      setDashboard(newDashboard);
      
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: aiMessage 
      }]);

    } catch (error) {
      console.error("Failed to mutate dashboard", error);
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: "Sorry, I encountered an error updating the dashboard. Please try again." 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AppLayout>
      <div className="flex h-[calc(100vh-64px)]">
        {/* Chat Sidebar */}
        <div className="w-1/3 min-w-[350px] border-r border-gray-800 flex flex-col bg-[#0D0F12]">
          <div className="p-4 border-b border-gray-800">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <Bot className="w-5 h-5 text-cyan-400" />
              Parity Assistant
            </h2>
            <p className="text-xs text-gray-500">AI-powered financial analysis</p>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4" ref={scrollRef}>
            {messages.map((msg, i) => (
              <div 
                key={i} 
                className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
              >
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-cyan-500/20 text-cyan-400' : 'bg-purple-500/20 text-purple-400'}`}>
                  {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>
                <div className={`p-3 rounded-lg text-sm max-w-[80%] ${msg.role === 'user' ? 'bg-cyan-500/10 text-cyan-100 border border-cyan-500/20' : 'bg-gray-800 text-gray-200 border border-gray-700'}`}>
                  {msg.content}
                </div>
              </div>
            ))}
            {isLoading && (
               <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400">
                    <Bot className="w-4 h-4" />
                  </div>
                  <div className="p-3 rounded-lg bg-gray-800 border border-gray-700 flex items-center gap-2 text-sm text-gray-400">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Thinking...
                  </div>
               </div>
            )}
          </div>

           {/* Suggestions */}
           <div className="px-4 pt-2 pb-0 flex flex-wrap gap-2">
              {suggestions.map((s, i) => (
                  <button 
                    key={i}
                    onClick={() => handleSend(s)}
                    disabled={isLoading}
                    className="text-xs bg-gray-800 hover:bg-cyan-500/20 hover:text-cyan-400 border border-gray-700 rounded-full px-3 py-1 transition-all text-gray-400"
                  >
                    {s}
                  </button>
              ))}
           </div>

          {/* Input */}
          <div className="p-4 border-t border-gray-800 bg-[#0D0F12]">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                placeholder="Ask to visualize revenue..."
                className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-white text-sm focus:outline-none focus:border-cyan-500 transition-colors"
                disabled={isLoading}
              />
              <button 
                onClick={() => handleSend()}
                disabled={isLoading || !input.trim()}
                className="p-2 bg-cyan-500 hover:bg-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed text-black rounded-lg transition-colors"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>

        {/* Dashboard Area */}
        <div className="flex-1 overflow-y-auto p-8 bg-black/50">
           <div className="max-w-5xl mx-auto">
             <div className="flex items-center justify-between mb-6">
                <h1 className="text-2xl font-bold text-white">Live Dashboard</h1>
                <span className="text-xs px-2 py-1 bg-green-500/10 text-green-400 rounded border border-green-500/20">Connected to Parity AI</span>
             </div>
             
             <motion.div
                key={JSON.stringify(dashboard)} // Force re-render animation on update
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
             >
                <DynamicDashboard schema={dashboard} />
             </motion.div>
           </div>
        </div>
      </div>
    </AppLayout>
  );
}
