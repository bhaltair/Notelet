import type { RuntimeEvent } from "../types";

type RuntimeEventsProps = {
  events: RuntimeEvent[];
  onClear: () => void;
};

export function RuntimeEvents({ events, onClear }: RuntimeEventsProps) {
  return (
    <aside className="panel event-panel" aria-labelledby="eventsTitle">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Trace</p>
          <h2 id="eventsTitle">Runtime Events</h2>
        </div>
        <button className="ghost-button" onClick={onClear} type="button">
          Clear
        </button>
      </div>
      <ol className="event-log">
        {events.length === 0 ? (
          <li className="empty-state">No events yet.</li>
        ) : (
          events.map((event, index) => (
            <li className={`event-item ${event.type}`} key={`${event.type}-${index}`}>
              <span className="event-type">{event.type}</span>
              <p className="event-summary">{summarizeEvent(event)}</p>
              <pre className="event-json">{JSON.stringify(event, null, 2)}</pre>
            </li>
          ))
        )}
      </ol>
    </aside>
  );
}

function summarizeEvent(event: RuntimeEvent): string {
  switch (event.type) {
    case "answer_delta":
      return `+ ${event.content}`;
    case "final_answer":
      return "Assistant answer completed.";
    case "model_response":
      return `${event.model} returned ${event.tool_call_count} tool call(s).`;
    case "tool_call":
      return `Calling ${event.name}.`;
    case "tool_result":
      return event.is_error ? `${event.name} failed.` : `${event.name} completed.`;
    case "tool_error":
      return `${event.name}: ${event.message}`;
    case "user_message":
      return "User message accepted.";
    case "error":
      return event.message;
  }
}
