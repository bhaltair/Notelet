import { useEffect, useState } from "react";
import { fetchHealth, fetchNotes, streamChat } from "./api";
import { ChatStream } from "./components/ChatStream";
import { Composer } from "./components/Composer";
import { MemoryPanel } from "./components/MemoryPanel";
import { RuntimeEvents } from "./components/RuntimeEvents";
import { StatusBar } from "./components/StatusBar";
import type { ChatMessage, RuntimeEvent } from "./types";
import "./styles.css";

type StreamState = "idle" | "streaming" | "error";

export function App() {
  const [model, setModel] = useState("");
  const [streamState, setStreamState] = useState<StreamState>("idle");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [events, setEvents] = useState<RuntimeEvent[]>([]);
  const [notes, setNotes] = useState("Loading notes...");

  useEffect(() => {
    fetchHealth()
      .then((payload) => setModel(payload.model))
      .catch((error: unknown) => {
        setStreamState("error");
        appendRuntimeEvent({
          type: "error",
          message: errorMessage(error),
        });
      });
    refreshNotes();
  }, []);

  async function refreshNotes() {
    try {
      setNotes(await fetchNotes());
    } catch (error) {
      setNotes(`Unable to load notes: ${errorMessage(error)}`);
    }
  }

  async function handleSend(message: string) {
    const agentMessageId = crypto.randomUUID();
    let sawError = false;
    setStreamState("streaming");

    // 先创建一个空的 Agent 气泡。后续每收到 answer_delta，
    // 就把 delta.content 追加到这个气泡里，形成“边生成边显示”的效果。
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: message },
      { id: agentMessageId, role: "agent", content: "" },
    ]);

    try {
      await streamChat(message, (event) => {
        // 所有 SSE 事件都先进入右侧 Runtime Events 时间线，方便调试 agent 行为。
        console.debug("[RuntimeEvent] received", event);
        appendRuntimeEvent(event);
        if (event.type === "answer_delta") {
          // answer_delta 只是一段增量文本，不是完整回答。
          // 完整回答由后端 final_answer 事件表示；UI 这里实时拼接显示。
          console.debug("[RuntimeEvent] append answer delta", {
            agentMessageId,
            content: event.content,
          });
          appendAgentDelta(agentMessageId, event.content);
        }
        if (event.type === "tool_result" && !event.is_error) {
          // 工具成功可能改变 notes.db，例如 add_note。
          // 所以收到成功 tool_result 后刷新 Memory 面板。
          console.debug("[RuntimeEvent] refresh memory after tool result", event);
          refreshNotes();
        }
        if (event.type === "error" || event.type === "tool_error") {
          // error 是 API/SSE 层错误；tool_error 是 agent 工具执行错误。
          // 两者都保留在事件时间线，并把顶部状态切到 Error。
          console.debug("[RuntimeEvent] mark stream error", event);
          sawError = true;
          setStreamState("error");
        }
      });
      setStreamState(sawError ? "error" : "idle");
    } catch (error) {
      const messageText = errorMessage(error);
      appendRuntimeEvent({ type: "error", message: messageText });
      appendAgentDelta(agentMessageId, `Request failed: ${messageText}`);
      setStreamState("error");
    } finally {
      refreshNotes();
    }
  }

  function appendRuntimeEvent(event: RuntimeEvent) {
    setEvents((current) => [...current, event]);
  }

  function appendAgentDelta(agentMessageId: string, delta: string) {
    setMessages((current) =>
      current.map((message) =>
        message.id === agentMessageId
          ? { ...message, content: message.content + delta }
          : message,
      ),
    );
  }

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">Notelet v0.0.6</p>
          <h1>Runtime Console</h1>
          <p className="lede">
            A React/Vite workbench for inspecting streaming assistant output,
            local tool calls, tool results, and SQLite-backed memory.
          </p>
        </div>
        <StatusBar model={model} state={streamState} />
      </header>

      <section className="workspace">
        <section className="panel chat-panel" aria-labelledby="chatTitle">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Conversation</p>
              <h2 id="chatTitle">Chat Stream</h2>
            </div>
            <span className={`status-pill ${streamState}`}>
              {streamState === "streaming"
                ? "Streaming"
                : streamState === "error"
                  ? "Error"
                  : "Idle"}
            </span>
          </div>
          <div className="chat-log" aria-live="polite">
            <ChatStream messages={messages} />
          </div>
          <Composer disabled={streamState === "streaming"} onSend={handleSend} />
        </section>

        <RuntimeEvents events={events} onClear={() => setEvents([])} />
      </section>

      <MemoryPanel notes={notes} onRefresh={refreshNotes} />
    </main>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
