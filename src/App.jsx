import { useState, useRef, useEffect } from "react";
import "./index.css";

const SUGGESTIONS = [
  "Explain a complex topic simply",
  "Help me brainstorm ideas",
  "Write better code",
  "Summarize something for me",
  "Teach me something new"
];

// 🔹 Available models
const MODELS = [
  { id: "mistral", label: "Mistral" },
  { id: "llama3", label: "LLaMA 3" },
  { id: "gemma", label: "Gemma" }
];

export default function App() {
  const [chats, setChats] = useState([
    { id: 1, title: "New chat", messages: [] }
  ]);
  const [activeId, setActiveId] = useState(1);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  // sidebar toggle
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // theme
  const [theme, setTheme] = useState(
    localStorage.getItem("theme") || "dark"
  );

  // 🔹 model selection
  const [model, setModel] = useState(
    localStorage.getItem("model") || MODELS[0].id
  );

  const controllerRef = useRef(null);
  const bottomRef = useRef(null);

  const activeChat = chats.find(c => c.id === activeId);

  /* ---------- theme persistence ---------- */
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
  }, [theme]);

  /* ---------- model persistence ---------- */
  useEffect(() => {
    localStorage.setItem("model", model);
  }, [model]);

  /* ---------- auto scroll ---------- */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeChat?.messages]);

  /* ---------- new chat ---------- */
  const newChat = () => {
    const id = Date.now();
    setChats(prev => [
      { id, title: "New chat", messages: [] },
      ...prev
    ]);
    setActiveId(id);
    setInput("");
  };

  /* ---------- send message ---------- */
  const send = async (text) => {
    const content = text ?? input;
    if (!content.trim() || loading) return;

    const userMsg = { role: "user", content };
    const aiMsg = { role: "assistant", content: "" };

    const historySnapshot = activeChat.messages
      .map(m => `${m.role === "user" ? "User" : "Assistant"}: ${m.content}`)
      .concat(`User: ${content}`);

    setChats(prev =>
      prev.map(c =>
        c.id === activeId
          ? {
              ...c,
              title: c.messages.length === 0
                ? content.slice(0, 32)
                : c.title,
              messages: [...c.messages, userMsg, aiMsg]
            }
          : c
      )
    );

    setInput("");
    setLoading(true);

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          message: content,
          history: historySnapshot,
          model // 🔹 send selected model
        })
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        aiMsg.content += decoder.decode(value);

        setChats(prev =>
          prev.map(c =>
            c.id === activeId
              ? { ...c, messages: [...c.messages.slice(0, -1), aiMsg] }
              : c
          )
        );
      }
    } finally {
      setLoading(false);
      controllerRef.current = null;
    }
  };

  /* ---------- stop ---------- */
  const stop = () => {
    controllerRef.current?.abort();
    setLoading(false);
  };

  const isEmpty = activeChat.messages.length === 0;

  return (
    <div className="app">
      {/* ---------- Sidebar ---------- */}
      {sidebarOpen && (
        <aside className="sidebar">
          <button className="new-chat" onClick={newChat}>
            + New chat
          </button>

          {/* Vercel Status Badge */}
          <div style={{
            margin: "0 16px",
            padding: "8px",
            borderRadius: "6px",
            background: "rgba(16, 185, 129, 0.1)",
            color: "#10b981",
            fontSize: "12px",
            fontWeight: "bold",
            display: "flex",
            alignItems: "center",
            gap: "6px",
            marginTop: "16px"
          }}>
            <span style={{ display: "inline-block", width: "8px", height: "8px", background: "#10b981", borderRadius: "50%" }}></span>
            Vercel Deploy: Live
          </div>

          {/* 🔹 Model selector */}
          <select
            value={model}
            onChange={e => setModel(e.target.value)}
            style={{
              marginTop: 10,
              padding: "8px",
              borderRadius: 10,
              background: "transparent",
              color: "inherit",
              border: "1px solid rgba(255,255,255,0.15)"
            }}
          >
            {MODELS.map(m => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>

          <button
            className="theme-toggle"
            onClick={() =>
              setTheme(theme === "dark" ? "light" : "dark")
            }
          >
            {theme === "dark" ? "🌞 Light mode" : "🌙 Dark mode"}
          </button>

          <div className="chat-list">
            {chats.map(chat => (
              <div
                key={chat.id}
                className={`chat-item ${
                  chat.id === activeId ? "active" : ""
                }`}
                onClick={() => setActiveId(chat.id)}
              >
                {chat.title}
              </div>
            ))}
          </div>
        </aside>
      )}

      {/* ---------- Main ---------- */}
      <main className="main">
        {/* hamburger */}
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          style={{
            position: "fixed",
            top: 16,
            left: sidebarOpen ? 276 : 16,
            zIndex: 1000,
            background: "transparent",
            border: "none",
            fontSize: 22,
            cursor: "pointer",
            color: "inherit"
          }}
        >
          ☰
        </button>

        <div className="chat-area">
          {isEmpty && (
            <div className="empty">
              <h1>Hello.</h1>
              <p>How can I help today?</p>

              <div className="suggestions">
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {activeChat.messages.map((m, i) => (
            <div key={i} className={`card ${m.role}`}>
              {m.content}
            </div>
          ))}

          <div ref={bottomRef} />
        </div>

        <div
  className="input-shell"
  style={{
    left: sidebarOpen ? "calc(260px + 50%)" : "50%",
    width: sidebarOpen
      ? "min(760px, calc(100% - 300px))"
      : "min(760px, calc(100% - 40px))",
    transform: "translateX(-50%)"
  }}
>

          <textarea
            value={input}
            placeholder="Ask anything…"
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          {!loading ? (
            <button onClick={() => send()}>Send</button>
          ) : (
            <button className="stop" onClick={stop}>
              Stop
            </button>
          )}
        </div>
      </main>
    </div>
  );
}
