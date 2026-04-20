const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const chatLog = document.querySelector("#chatLog");
const eventLog = document.querySelector("#eventLog");
const memoryLog = document.querySelector("#memoryLog");
const streamState = document.querySelector("#streamState");
const refreshNotesButton = document.querySelector("#refreshNotesButton");
const clearEventsButton = document.querySelector("#clearEventsButton");

let hasChatMessages = false;
let hasEvents = false;

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) {
    return;
  }

  appendMessage("user", message);
  messageInput.value = "";
  await sendMessage(message);
});

refreshNotesButton.addEventListener("click", () => {
  refreshNotes();
});

clearEventsButton.addEventListener("click", () => {
  hasEvents = false;
  eventLog.innerHTML = '<li class="empty-state">No events yet.</li>';
});

async function sendMessage(message) {
  setStreaming(true);
  const agentMessage = appendMessage("agent", "");

  try {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
    });

    if (!response.ok || !response.body) {
      const error = await readError(response);
      throw new Error(error);
    }

    await readSseStream(response.body, (event) => {
      appendEvent(event);
      if (event.type === "answer_delta") {
        agentMessage.querySelector(".message-body").textContent += event.content;
        chatLog.scrollTop = chatLog.scrollHeight;
      }
      if (event.type === "tool_result" && !event.is_error) {
        refreshNotes();
      }
      if (event.type === "error" || event.type === "tool_error") {
        setStatus("Error", "error");
      }
    });
  } catch (error) {
    const messageText = error instanceof Error ? error.message : String(error);
    appendEvent({ type: "error", message: messageText });
    agentMessage.querySelector(".message-body").textContent =
      `Request failed: ${messageText}`;
    setStatus("Error", "error");
  } finally {
    setStreaming(false);
    refreshNotes();
  }
}

async function readSseStream(body, onEvent) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const parsed = parseSseEvent(part);
      if (parsed) {
        onEvent(parsed);
      }
    }
  }

  buffer += decoder.decode();
  const parsed = parseSseEvent(buffer);
  if (parsed) {
    onEvent(parsed);
  }
}

function parseSseEvent(rawEvent) {
  const dataLine = rawEvent
    .split("\n")
    .find((line) => line.startsWith("data: "));
  if (!dataLine) {
    return null;
  }
  return JSON.parse(dataLine.slice("data: ".length));
}

function appendMessage(role, content) {
  if (!hasChatMessages) {
    chatLog.innerHTML = "";
    hasChatMessages = true;
  }

  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.innerHTML = `
    <span class="message-label">${role === "user" ? "You" : "Agent"}</span>
    <span class="message-body"></span>
  `;
  article.querySelector(".message-body").textContent = content;
  chatLog.append(article);
  chatLog.scrollTop = chatLog.scrollHeight;
  return article;
}

function appendEvent(event) {
  if (!hasEvents) {
    eventLog.innerHTML = "";
    hasEvents = true;
  }

  const item = document.createElement("li");
  item.className = `event-item ${event.type}`;
  item.innerHTML = `
    <span class="event-type"></span>
    <pre class="event-json"></pre>
  `;
  item.querySelector(".event-type").textContent = event.type;
  item.querySelector(".event-json").textContent = JSON.stringify(event, null, 2);
  eventLog.append(item);
  eventLog.scrollTop = eventLog.scrollHeight;
}

async function refreshNotes() {
  try {
    const response = await fetch("/api/notes");
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const payload = await response.json();
    memoryLog.textContent = payload.notes;
  } catch (error) {
    const messageText = error instanceof Error ? error.message : String(error);
    memoryLog.textContent = `Unable to load notes: ${messageText}`;
  }
}

async function readError(response) {
  try {
    const payload = await response.json();
    return payload.error || `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

function setStreaming(isStreaming) {
  messageInput.disabled = isStreaming;
  sendButton.disabled = isStreaming;
  if (isStreaming) {
    setStatus("Streaming", "streaming");
  } else if (!streamState.classList.contains("error")) {
    setStatus("Idle", "");
  }
}

function setStatus(label, stateClass) {
  streamState.textContent = label;
  streamState.className = "status-pill";
  if (stateClass) {
    streamState.classList.add(stateClass);
  }
}

refreshNotes();
