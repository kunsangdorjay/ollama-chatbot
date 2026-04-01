import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import jsPDF from "jspdf";
import "./index.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const CHATS_KEY = "claude_like_chats_v1";
const SETTINGS_KEY = "claude_like_settings_v1";

const DEFAULT_SETTINGS = {
  model: "llama3.2",
  temperature: 0.7,
  maxTokens: 2000,
  systemPrompt: "",
  theme: "dark",
  tools: {
    calculator: true,
    wikipedia: true,
    weather: true,
    urlFetch: true
  }
};

const SUGGESTIONS = [
  "Plan a study schedule for this week",
  "Explain transformers in simple terms",
  "Help me debug a React issue",
  "Write a cleaner version of my message"
];

const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

const formatTime = (ts) =>
  new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

function getPreview(chat) {
  const last = [...chat.messages].reverse().find((m) => m.role === "user");
  return last?.content?.slice(0, 54) || "No messages yet";
}

export default function App() {
  const [chats, setChats] = useState(() => {
    const raw = localStorage.getItem(CHATS_KEY);
    if (raw) return JSON.parse(raw);
    const id = uid();
    return [{ id, title: "New chat", updatedAt: Date.now(), messages: [] }];
  });
  const [activeId, setActiveId] = useState(() => {
    const raw = localStorage.getItem(CHATS_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    return data[0]?.id || null;
  });
  const [settings, setSettings] = useState(() => {
    const raw = localStorage.getItem(SETTINGS_KEY);
    return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : DEFAULT_SETTINGS;
  });
  const [models, setModels] = useState(["llama3.2", "mistral", "gemma3"]);
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [search, setSearch] = useState("");
  const [messageSearch, setMessageSearch] = useState("");
  const [input, setInput] = useState("");
  const [pendingFiles, setPendingFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [recording, setRecording] = useState(false);
  const [recordingError, setRecordingError] = useState("");
  const [editingMessageId, setEditingMessageId] = useState(null);

  const controllerRef = useRef(null);
  const bottomRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const recognitionRef = useRef(null);

  const activeChat = chats.find((c) => c.id === activeId) || chats[0];

  useEffect(() => {
    if (!activeId && chats.length) setActiveId(chats[0].id);
  }, [activeId, chats]);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", settings.theme);
    localStorage.setItem(CHATS_KEY, JSON.stringify(chats));
  }, [chats, settings.theme]);

  useEffect(() => {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }, [settings]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [activeChat?.messages, loading]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [input]);

  useEffect(() => {
    fetch(`${API_URL}/models`)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data.models) && data.models.length) setModels(data.models);
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        newChat();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === ",") {
        e.preventDefault();
        setShowSettings(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const visibleChats = useMemo(
    () =>
      chats
        .filter((c) => c.title.toLowerCase().includes(search.toLowerCase()) || getPreview(c).toLowerCase().includes(search.toLowerCase()))
        .sort((a, b) => b.updatedAt - a.updatedAt),
    [chats, search]
  );

  const newChat = () => {
    const id = uid();
    setChats((prev) => [{ id, title: "New chat", updatedAt: Date.now(), messages: [] }, ...prev]);
    setActiveId(id);
    setInput("");
    setPendingFiles([]);
  };

  const updateActiveChat = (updater) => {
    setChats((prev) =>
      prev.map((c) => {
        if (c.id !== activeChat.id) return c;
        const next = updater(c);
        return { ...next, updatedAt: Date.now() };
      })
    );
  };

  const deleteChat = (id) => {
    if (!window.confirm("Delete this conversation?")) return;
    setChats((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (!next.length) {
        const newId = uid();
        setActiveId(newId);
        return [{ id: newId, title: "New chat", updatedAt: Date.now(), messages: [] }];
      }
      if (activeId === id) setActiveId(next[0].id);
      return next;
    });
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(activeChat, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${activeChat.title || "conversation"}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const exportMarkdown = () => {
    const md = (activeChat?.messages || [])
      .map((m) => `## ${m.role === "user" ? "User" : "Assistant"}\n\n${m.content}\n`)
      .join("\n");
    const blob = new Blob([md], { type: "text/markdown" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${activeChat.title || "conversation"}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const exportPdf = () => {
    const doc = new jsPDF();
    doc.setFontSize(12);
    let y = 12;
    (activeChat?.messages || []).forEach((m) => {
      const lines = doc.splitTextToSize(`${m.role === "user" ? "User" : "Assistant"}: ${m.content}`, 180);
      if (y + lines.length * 6 > 280) {
        doc.addPage();
        y = 12;
      }
      doc.text(lines, 12, y);
      y += lines.length * 6 + 4;
    });
    doc.save(`${activeChat.title || "conversation"}.pdf`);
  };

  const handleFiles = async (files) => {
    const list = Array.from(files || []);
    const valid = list.filter((f) => f.size <= 8 * 1024 * 1024);
    const processed = await Promise.all(
      valid.map(
        (file) =>
          new Promise((resolve) => {
            if (file.type.startsWith("image/")) {
              const reader = new FileReader();
              reader.onload = () =>
                resolve({
                  id: uid(),
                  kind: "image",
                  name: file.name,
                  size: file.size,
                  preview: URL.createObjectURL(file),
                  data: String(reader.result).split(",")[1]
                });
              reader.readAsDataURL(file);
              return;
            }

            file
              .text()
              .then((text) =>
                resolve({
                  id: uid(),
                  kind: "document",
                  name: file.name,
                  size: file.size,
                  mime: file.type,
                  content: text.slice(0, 12000)
                })
              )
              .catch(() =>
                resolve({
                  id: uid(),
                  kind: "document",
                  name: file.name,
                  size: file.size,
                  mime: file.type,
                  content: `[Unable to parse ${file.name}.]`
                })
              );
          })
      )
    );
    setPendingFiles((prev) => [...prev, ...processed]);
  };

  const startVoice = () => {
    const API = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!API) {
      setRecordingError("Speech recognition is not supported in this browser.");
      return;
    }
    const recognition = new API();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      let text = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        text += event.results[i][0].transcript;
      }
      setInput((prev) => `${prev} ${text}`.trim());
    };
    recognition.onerror = () => setRecordingError("Microphone permission was denied or unavailable.");
    recognition.onend = () => setRecording(false);
    recognitionRef.current = recognition;
    setRecordingError("");
    setRecording(true);
    recognition.start();
  };

  const stopVoice = () => {
    recognitionRef.current?.stop();
    setRecording(false);
  };

  const send = async (rawText) => {
    const content = (rawText ?? input).trim();
    if ((!content && pendingFiles.length === 0) || loading) return;

    const now = Date.now();
    const userMsg = {
      id: uid(),
      role: "user",
      content: content || "Analyze attached image(s).",
      createdAt: now,
      attachments: pendingFiles.map((f) => ({
        id: f.id,
        kind: f.kind,
        name: f.name,
        preview: f.preview
      }))
    };
    const aiMsg = { id: uid(), role: "assistant", content: "", createdAt: now + 1 };

    const historySnapshot = activeChat.messages
      .map((m) => `${m.role === "user" ? "User" : "Assistant"}: ${m.content}`)
      .concat(`User: ${userMsg.content}`);

    updateActiveChat((c) => ({
      ...c,
      title: c.messages.length === 0 ? userMsg.content.slice(0, 42) || "Image chat" : c.title,
      messages: [...c.messages, userMsg, aiMsg]
    }));

    const outgoingFiles = pendingFiles;
    setPendingFiles([]);
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const res = await fetch(`${API_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
          message: userMsg.content,
          history: historySnapshot,
          model: settings.model,
          temperature: settings.temperature,
          attachments: outgoingFiles.map((f) => ({
            kind: f.kind,
            name: f.name,
            data: f.data,
            content: f.content,
            mime: f.mime
          })),
          enabled_tools: settings.tools
        })
      });

      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      if (!res.body) throw new Error("Empty response body from server");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let partial = "";
      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          let event;
          try {
            event = JSON.parse(line);
          } catch {
            continue;
          }
          if (event.type === "token") {
            partial += event.data || "";
            updateActiveChat((c) => {
              const nextMessages = [...c.messages];
              const idx = nextMessages.findIndex((m) => m.id === aiMsg.id);
              if (idx >= 0) nextMessages[idx] = { ...nextMessages[idx], content: partial };
              return { ...c, messages: nextMessages };
            });
          } else if (event.type === "tool") {
            partial += `\n[Tool] ${event.data?.tool || "tool"}: ${JSON.stringify(event.data?.result || {})}\n`;
            updateActiveChat((c) => {
              const nextMessages = [...c.messages];
              const idx = nextMessages.findIndex((m) => m.id === aiMsg.id);
              if (idx >= 0) nextMessages[idx] = { ...nextMessages[idx], content: partial };
              return { ...c, messages: nextMessages };
            });
          } else if (event.type === "error") {
            throw new Error(event.data?.message || "Streaming error");
          }
        }
      }
    } catch (err) {
      const message = err?.name === "AbortError" ? "[Stopped by user]" : "Connection error. Check backend server.";
      updateActiveChat((c) => {
        const nextMessages = [...c.messages];
        const idx = nextMessages.findIndex((m) => m.id === aiMsg.id);
        if (idx >= 0) nextMessages[idx] = { ...nextMessages[idx], content: message };
        return { ...c, messages: nextMessages };
      });
    } finally {
      setLoading(false);
      controllerRef.current = null;
    }
  };

  const stop = () => {
    controllerRef.current?.abort();
    setLoading(false);
  };

  const regenerateLast = () => {
    if (loading || !activeChat?.messages?.length) return;
    const lastUser = [...activeChat.messages].reverse().find((m) => m.role === "user");
    if (!lastUser) return;
    updateActiveChat((c) => ({
      ...c,
      messages: c.messages.filter((m, idx) => idx < c.messages.length - 1 || m.role === "user")
    }));
    send(lastUser.content);
  };

  const saveEditedMessage = (id, content) => {
    updateActiveChat((c) => {
      const idx = c.messages.findIndex((m) => m.id === id);
      if (idx === -1) return c;
      const updated = [...c.messages];
      updated[idx] = { ...updated[idx], content };
      return { ...c, messages: updated.slice(0, idx + 1) };
    });
    setEditingMessageId(null);
    send(content);
  };

  const isEmpty = !activeChat?.messages.length;

  return (
    <div
      className="app"
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        handleFiles(e.dataTransfer.files);
      }}
    >
      {dragging && <div className="drop-overlay">Drop files to attach</div>}
      <aside className={`sidebar ${sidebarOpen ? "" : "collapsed"}`}>
        <div className="sidebar-top">
          <button className="new-chat" aria-label="Create new chat" onClick={newChat}>+ New chat</button>
          <button className="ghost" aria-label="Open settings" onClick={() => setShowSettings(true)}>Settings</button>
          <div className="export-row">
            <button className="ghost" onClick={exportJson}>JSON</button>
            <button className="ghost" onClick={exportMarkdown}>MD</button>
            <button className="ghost" onClick={exportPdf}>PDF</button>
          </div>
          <input
            className="search"
            placeholder="Search conversations"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="chat-list">
          {visibleChats.map((chat) => (
            <div key={chat.id} className={`chat-item ${chat.id === activeId ? "active" : ""}`}>
              <button className="chat-hit" onClick={() => setActiveId(chat.id)}>
                <div className="chat-title">{chat.title}</div>
                <div className="chat-meta">{getPreview(chat)} - {formatTime(chat.updatedAt)}</div>
              </button>
              <button className="delete-btn" onClick={() => deleteChat(chat.id)}>x</button>
            </div>
          ))}
        </div>
      </aside>

      <main className="main">
        <button className="sidebar-toggle" aria-label="Toggle sidebar" onClick={() => setSidebarOpen((s) => !s)}>☰</button>

        <section className="thread">
          <div className="thread-toolbar">
            <input
              className="search"
              placeholder="Search in this chat"
              value={messageSearch}
              onChange={(e) => setMessageSearch(e.target.value)}
            />
            <button className="ghost" onClick={regenerateLast}>Regenerate</button>
          </div>
          {isEmpty && (
            <div className="empty">
              <h1>How can I help you today?</h1>
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} className="ghost" onClick={() => send(s)}>{s}</button>
                ))}
              </div>
            </div>
          )}

          {activeChat?.messages
            .filter((m) => !messageSearch || m.content.toLowerCase().includes(messageSearch.toLowerCase()))
            .map((m) => (
            <article key={m.id} className={`message ${m.role}`}>
              {m.role === "assistant" && <div className="avatar">AI</div>}
              <div className="bubble" title={new Date(m.createdAt).toLocaleString()}>
                <div className="content">
                  {editingMessageId === m.id && m.role === "user" ? (
                    <EditMessageForm
                      initialValue={m.content}
                      onCancel={() => setEditingMessageId(null)}
                      onSave={(value) => saveEditedMessage(m.id, value)}
                    />
                  ) : (
                    <MarkdownMessage text={m.content || (loading ? "..." : "")} />
                  )}
                </div>
                {!!m.attachments?.length && (
                  <div className="attachment-grid">
                    {m.attachments.map((f) => (
                      f.kind === "image" ? (
                        <img key={f.id} src={f.preview} alt={f.name} className="thumb" />
                      ) : (
                        <div key={f.id} className="doc-thumb">{f.name}</div>
                      )
                    ))}
                  </div>
                )}
                <time className="timestamp">{formatTime(m.createdAt)}</time>
                <div className="msg-actions">
                  <button className="ghost" onClick={() => navigator.clipboard.writeText(m.content || "")}>Copy</button>
                  {m.role === "user" && <button className="ghost" onClick={() => setEditingMessageId(m.id)}>Edit</button>}
                </div>
              </div>
            </article>
          ))}

          {loading && (
            <article className="message assistant">
              <div className="avatar">AI</div>
              <div className="bubble">
                <TypingDots />
              </div>
            </article>
          )}
          <div ref={bottomRef} />
        </section>

        <section className="composer-wrap">
          {!!pendingFiles.length && (
            <div className="pending-files">
              {pendingFiles.map((f) => (
                <div key={f.id} className="pending-chip">
                  {f.kind === "image" ? <img src={f.preview} alt={f.name} /> : <div className="doc-dot">DOC</div>}
                  <span>{f.name}</span>
                  <button onClick={() => setPendingFiles((prev) => prev.filter((x) => x.id !== f.id))}>x</button>
                </div>
              ))}
            </div>
          )}
          <div className="composer">
            <button className="icon-btn" onClick={() => fileInputRef.current?.click()} title="Attach files">📎</button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept="image/png,image/jpeg,image/webp,image/gif,.txt,.md,.json,.js,.jsx,.ts,.tsx,.py,.csv,.pdf,.docx"
              hidden
              onChange={(e) => handleFiles(e.target.files)}
            />
            <button className={`icon-btn ${recording ? "recording" : ""}`} onClick={recording ? stopVoice : startVoice} title="Voice input">🎤</button>
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              placeholder="How can I help you today?"
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <div className="composer-right">
              <small>{input.length}</small>
              {!loading ? (
                <button className="send" disabled={!input.trim() && pendingFiles.length === 0} onClick={() => send()}>
                  ➤
                </button>
              ) : (
                <button className="stop" onClick={stop}>Stop</button>
              )}
            </div>
          </div>
          {recordingError && <div className="hint error">{recordingError}</div>}
        </section>
      </main>

      {showSettings && (
        <div className="settings-modal" onClick={() => setShowSettings(false)}>
          <div className="settings-card" onClick={(e) => e.stopPropagation()}>
            <h3>Preferences</h3>
            <label>
              Theme
              <select value={settings.theme} onChange={(e) => setSettings((s) => ({ ...s, theme: e.target.value }))}>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </label>
            <label>
              Model
              <select value={settings.model} onChange={(e) => setSettings((s) => ({ ...s, model: e.target.value }))}>
                {models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </label>
            <label>
              Temperature: {settings.temperature.toFixed(1)}
              <input
                type="range"
                min="0"
                max="2"
                step="0.1"
                value={settings.temperature}
                onChange={(e) => setSettings((s) => ({ ...s, temperature: Number(e.target.value) }))}
              />
            </label>
            <label>
              Tools
              <div style={{ display: "grid", gap: 6 }}>
                {Object.entries(settings.tools).map(([key, value]) => (
                  <label key={key} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={value}
                      onChange={(e) =>
                        setSettings((s) => ({
                          ...s,
                          tools: { ...s.tools, [key]: e.target.checked }
                        }))
                      }
                    />
                    {key}
                  </label>
                ))}
              </div>
            </label>
            <button className="ghost" onClick={() => setShowSettings(false)}>Close</button>
          </div>
        </div>
      )}
    </div>
  );
}

function TypingDots() {
  return (
    <span className="dots" aria-label="Assistant is typing">
      <span />
      <span />
      <span />
    </span>
  );
}

function EditMessageForm({ initialValue, onSave, onCancel }) {
  const [value, setValue] = useState(initialValue);
  return (
    <div className="edit-form">
      <textarea value={value} onChange={(e) => setValue(e.target.value)} />
      <div className="edit-actions">
        <button className="ghost" onClick={onCancel}>Cancel</button>
        <button className="new-chat" onClick={() => onSave(value)}>Save & Resend</button>
      </div>
    </div>
  );
}

function MarkdownMessage({ text }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code(props) {
          const { inline, className, children, ...rest } = props;
          const match = /language-(\w+)/.exec(className || "");
          const codeText = String(children).replace(/\n$/, "");
          if (!inline && match) {
            return (
              <div className="code-wrap">
                <button className="ghost copy-code" onClick={() => navigator.clipboard.writeText(codeText)}>Copy code</button>
                <SyntaxHighlighter
                  {...rest}
                  PreTag="div"
                  language={match[1]}
                  style={oneDark}
                  customStyle={{ borderRadius: 10, margin: 0 }}
                >
                  {codeText}
                </SyntaxHighlighter>
              </div>
            );
          }
          return <code className={className} {...rest}>{children}</code>;
        }
      }}
    >
      {text}
    </ReactMarkdown>
  );
}
