"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, TrendingUp, Users, MessageSquare, PlayCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";

export default function Dashboard() {
  const [urlA, setUrlA] = useState("");
  const [urlB, setUrlB] = useState("");
  const [loading, setLoading] = useState(false);
  const [videoData, setVideoData] = useState<any[]>([]);

  const [chat, setChat] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  const handleIngest = async () => {
    if (!urlA || !urlB) return alert("Please enter both URLs");
    setLoading(true);
    setVideoData([]);

    try {
      const ingestPromises = [urlA, urlB].map(url =>
        fetch("http://localhost:8000/api/ingest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url })
        }).then(res => res.json())
      );

      const ingestResults = await Promise.all(ingestPromises);

      const dataPromises = ingestResults.map(res =>
        fetch(`http://localhost:8000/api/video/${res.metadata.video_id}`).then(r => r.json())
      );

      const fullData = await Promise.all(dataPromises);
      setVideoData(fullData.map(d => d.data.metadata));

      setChat([{ role: "assistant", content: "Videos successfully ingested! Ask me anything about their engagement, hooks, or performance." }]);
    } catch (error) {
      console.error(error);
      alert("Error processing videos. Check backend logs.");
    }
    setLoading(false);
  };

  const handleChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input || !videoData.length) return;

    const userMessage = input;
    setInput("");

    // 1. Snapshot the updated history locally to completely bypass React's async state lag
    const updatedChatHistory = [...chat, { role: "user", content: userMessage }];
    setChat(updatedChatHistory);
    setChatLoading(true);

    try {
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          video_ids: videoData.map((v) => v.video_id),
          // OPTIMIZATION: Keep the entire chat history in the UI, but 
          // only transmit the last 4 messages over the network to eliminate lag.
          history: updatedChatHistory.slice(-4),
        }),
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      // Initialize an empty assistant message slot in the UI chat history array
      setChat((prev) => [...prev, { role: "assistant", content: "" }]);

      let done = false;
      let accumulatedMessage = "";

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          accumulatedMessage += chunk;

          // Efficiently target and stream text directly into the final index item
          setChat((prev) => {
            const newChat = [...prev];
            if (newChat.length > 0) {
              newChat[newChat.length - 1] = {
                ...newChat[newChat.length - 1],
                content: accumulatedMessage,
              };
            }
            return newChat;
          });
        }
      }
    } catch (error) {
      console.error("Streaming failed:", error);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 overflow-hidden bg-[#0a0a0a] text-neutral-200 p-4 md:p-6 flex flex-col font-sans">

      {/* Header */}
      <header className="mb-6 flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-white flex items-center gap-3">
            <PlayCircle className="text-blue-500" size={28} />
            Creator Analytics
          </h1>
          <p className="text-neutral-500 text-sm mt-1 font-medium">Multi-Modal RAG Dashboard</p>
        </div>
      </header>

      {/* Input Command Bar */}
      <div className="flex flex-col md:flex-row gap-3 mb-6 bg-neutral-900/50 p-3 rounded-2xl border border-white/5 shadow-md shrink-0">
        <input
          type="text"
          placeholder="Video A URL (YouTube/IG)"
          className="flex-1 bg-neutral-950 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all text-sm"
          value={urlA}
          onChange={e => setUrlA(e.target.value)}
        />
        <input
          type="text"
          placeholder="Video B URL (YouTube/IG)"
          className="flex-1 bg-neutral-950 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all text-sm"
          value={urlB}
          onChange={e => setUrlB(e.target.value)}
        />
        <button
          onClick={handleIngest}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-500 text-white px-8 py-3 rounded-xl font-semibold transition-all disabled:opacity-50 flex items-center justify-center gap-2 shadow-lg"
        >
          {loading ? <Loader2 className="animate-spin" size={18} /> : <TrendingUp size={18} />}
          {loading ? "Analyzing..." : "Analyze Hooks"}
        </button>
      </div>

      {/* Main Layout Grid - min-h-0 prevents flex children from expanding out of bounds */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-6 min-h-0">

        {/* Left Column: Video Cards - scrolls independently */}
        <div className="lg:col-span-5 h-full overflow-y-auto pr-2 flex flex-col gap-5 pb-4 custom-scrollbar">
          {videoData.length === 0 && !loading && (
            <div className="h-48 flex flex-col items-center justify-center border-2 border-dashed border-neutral-800 rounded-2xl text-neutral-600 bg-neutral-900/20">
              <TrendingUp size={36} className="mb-3 opacity-20" />
              <p className="font-medium text-sm">Enter URLs above to begin.</p>
            </div>
          )}

          {videoData.map((vid, i) => (
            <div key={vid.video_id} className="bg-neutral-900/80 border border-white/10 rounded-2xl overflow-hidden shadow-xl backdrop-blur-sm shrink-0">
              <div className="aspect-video w-full relative bg-neutral-950 border-b border-white/5">
                {vid.platform === 'youtube' ? (
                  <img
                    src={`https://img.youtube.com/vi/${vid.video_id}/maxresdefault.jpg`}
                    alt={vid.title}
                    className="absolute inset-0 w-full h-full object-cover"
                    onError={(e) => {
                      e.currentTarget.src = `https://i.ytimg.com/vi/${vid.video_id}/hqdefault.jpg`;
                    }}
                  />
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center text-neutral-600 font-medium">IG Reel Data</div>
                )}
                <div className="absolute top-3 left-3 bg-black/80 backdrop-blur-md px-3 py-1.5 rounded-lg text-xs font-bold text-white tracking-widest border border-white/10">
                  VIDEO {i === 0 ? 'A' : 'B'}
                </div>
              </div>

              <div className="p-5">
                <h3 className="font-bold text-base text-white line-clamp-2 mb-2 leading-snug">{vid.title}</h3>
                <p className="text-neutral-400 text-xs mb-4 flex items-center gap-1.5 font-medium">
                  <Users size={14} className="text-neutral-500" /> {vid.creator}
                </p>

                <div className="grid grid-cols-3 gap-2">
                  <div className="bg-neutral-950/50 p-3 rounded-xl border border-white/5">
                    <p className="text-[10px] text-neutral-500 mb-1 uppercase tracking-wider font-semibold">Views</p>
                    <p className="font-mono text-sm font-medium text-neutral-200">{(vid.views).toLocaleString()}</p>
                  </div>
                  <div className="bg-neutral-950/50 p-3 rounded-xl border border-white/5">
                    <p className="text-[10px] text-neutral-500 mb-1 uppercase tracking-wider font-semibold">Engaged</p>
                    <p className="font-mono text-sm font-medium text-neutral-200">{(vid.likes + vid.comments).toLocaleString()}</p>
                  </div>
                  <div className="bg-blue-950/30 p-3 rounded-xl border border-blue-500/20">
                    <p className="text-[10px] text-blue-400 mb-1 uppercase tracking-wider font-semibold">Rate</p>
                    <p className="font-mono text-sm font-bold text-blue-400">{vid.engagement_rate}%</p>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Right Column: Chat Interface - strictly locked to h-full */}
        <div className="lg:col-span-7 bg-neutral-900/50 border border-white/10 rounded-2xl flex flex-col h-full shadow-2xl backdrop-blur-sm overflow-hidden">

          {/* Chat History - flex-1 allows it to take remaining space inside the box and scroll */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5 custom-scrollbar">
            {chat.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-neutral-500 gap-4">
                <div className="p-4 bg-neutral-800/50 rounded-full border border-white/5">
                  <MessageSquare size={28} className="text-neutral-400" />
                </div>
                <p className="font-medium text-sm">Waiting for system initialization...</p>
              </div>
            ) : (
              chat.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[90%] md:max-w-[85%] rounded-2xl px-5 py-3.5 shadow-sm ${msg.role === 'user'
                    ? 'bg-blue-600 text-white rounded-tr-sm'
                    : 'bg-neutral-800 text-neutral-200 border border-white/10 rounded-tl-sm'
                    }`}>
                    {msg.role === 'user' ? (
                      <p className="text-sm font-medium">{msg.content}</p>
                    ) : (
                      <div className="prose prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-headings:text-white prose-a:text-blue-400">
                        <ReactMarkdown>
                          {msg.content || "..."}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Chat Input Area - shrink-0 pins it to the bottom */}
          <div className="p-4 bg-neutral-950/80 border-t border-white/5 shrink-0">
            <form onSubmit={handleChat} className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder={videoData.length ? "E.g., Compare the hooks in the first 5 seconds..." : "Awaiting video ingestion..."}
                disabled={!videoData.length || chatLoading}
                className="flex-1 bg-neutral-900 border border-white/10 rounded-xl px-4 py-3 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/50 transition-all text-sm disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!input || !videoData.length || chatLoading}
                className="bg-white text-black px-5 rounded-xl font-semibold transition-all hover:bg-neutral-200 disabled:opacity-50 disabled:hover:bg-white flex items-center justify-center"
              >
                <Send size={18} />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}