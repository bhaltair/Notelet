type StatusBarProps = {
  model: string;
  state: "idle" | "streaming" | "error";
};

export function StatusBar({ model, state }: StatusBarProps) {
  const label = state === "streaming" ? "Streaming" : state === "error" ? "Error" : "Idle";

  return (
    <dl className="runtime-card" aria-label="Runtime status">
      <div>
        <dt>Model</dt>
        <dd>{model || "Loading..."}</dd>
      </div>
      <div>
        <dt>Transport</dt>
        <dd>SSE stream</dd>
      </div>
      <div>
        <dt>Frontend</dt>
        <dd>React + Vite</dd>
      </div>
      <div>
        <dt>Status</dt>
        <dd className={`status-word ${state}`}>{label}</dd>
      </div>
    </dl>
  );
}
