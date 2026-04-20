import type { ChatMessage } from "../types";

type ChatStreamProps = {
  messages: ChatMessage[];
};

export function ChatStream({ messages }: ChatStreamProps) {
  if (messages.length === 0) {
    return (
      <article className="empty-state">
        Ask Notelet to remember something, then watch the React console render
        the stream and runtime events as they arrive.
      </article>
    );
  }

  return (
    <>
      {messages.map((message) => (
        <article className={`message ${message.role}`} key={message.id}>
          <span className="message-label">
            {message.role === "user" ? "You" : "Agent"}
          </span>
          <span className="message-body">{message.content}</span>
        </article>
      ))}
    </>
  );
}
