import type { HealthPayload, NotesPayload, RuntimeEvent } from "./types";

export async function fetchHealth(): Promise<HealthPayload> {
  const response = await fetch("/health");
  if (!response.ok) {
    throw new Error(`Health check failed with HTTP ${response.status}`);
  }
  return response.json();
}

export async function fetchNotes(): Promise<string> {
  const response = await fetch("/api/notes");
  if (!response.ok) {
    throw new Error(`Notes request failed with HTTP ${response.status}`);
  }
  const payload = (await response.json()) as NotesPayload;
  return payload.notes;
}

export async function streamChat(
  message: string,
  onEvent: (event: RuntimeEvent) => void,
): Promise<void> {
  // 端到端 streaming 的第三段：React 通过 POST 把用户输入发给 Flask。
  // 这里不用 EventSource，因为 EventSource 只能发 GET，不能带 JSON body。
  // fetch 返回的 response.body 是 ReadableStream，里面是一段持续到来的 SSE 字节流。
  console.debug("[SSE] POST /api/chat/stream", { message });
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok || !response.body) {
    throw new Error(await readError(response));
  }

  console.debug("[SSE] stream opened", {
    status: response.status,
    contentType: response.headers.get("content-type"),
  });

  // readSseStream 会把 Flask 发来的文本帧重新解析成 RuntimeEvent，
  // 每解析出一个事件就调用 onEvent，让 App.tsx 决定怎么更新 UI。
  await readSseStream(response.body, onEvent);
  console.debug("[SSE] stream closed");
}

async function readSseStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: RuntimeEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    // value 是浏览器当前收到的一段二进制网络 chunk。
    // 注意：网络 chunk 不等于 SSE 事件边界。
    // 可能一个 chunk 里有半个事件，也可能有多个事件。
    // 所以先用 TextDecoder 转成字符串累积到 buffer，再按 SSE 的空行分隔符拆分。
    const decoded = decoder.decode(value, { stream: true });
    console.debug("[SSE] raw chunk", {
      byteLength: value.byteLength,
      text: decoded,
    });
    buffer += decoded;
    const parts = buffer.split("\n\n");

    // 最后一段可能是不完整事件，留在 buffer，等待下一次 reader.read() 补齐。
    buffer = parts.pop() ?? "";
    console.debug("[SSE] split chunk", {
      completeEvents: parts.length,
      pendingBuffer: buffer,
    });

    for (const part of parts) {
      const event = parseSseEvent(part);
      if (event) {
        // onEvent 是 App.tsx 传进来的回调；它会根据 event.type 分发到：
        // - answer_delta: 追加到 Agent 消息气泡
        // - tool_call/tool_result/tool_error: 追加到 Runtime Events 时间线
        // - final_answer: 标记完整回答已结束
        console.debug("[SSE] parsed event", event);
        onEvent(event);
      }
    }
  }

  // reader.done 后，TextDecoder 可能还有一点内部缓存；flush 后再解析最后残留事件。
  buffer += decoder.decode();
  console.debug("[SSE] flush buffer", { buffer });
  const event = parseSseEvent(buffer);
  if (event) {
    console.debug("[SSE] parsed final event", event);
    onEvent(event);
  }
}

function parseSseEvent(rawEvent: string): RuntimeEvent | null {
  // Flask 发来的单个事件长这样：
  //
  // event: answer_delta
  // data: {"type":"answer_delta","content":"Saved"}
  //
  // 这里真正驱动 React 状态的是 data 行里的 JSON。
  // event 行主要方便浏览器 DevTools/协议层分类；payload 自己也带 type 字段。
  const dataLine = rawEvent
    .split("\n")
    .find((line) => line.startsWith("data: "));
  if (!dataLine) {
    if (rawEvent.trim()) {
      console.debug("[SSE] ignored frame without data line", rawEvent);
    }
    return null;
  }
  return JSON.parse(dataLine.slice("data: ".length)) as RuntimeEvent;
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { error?: string };
    return payload.error ?? `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}
