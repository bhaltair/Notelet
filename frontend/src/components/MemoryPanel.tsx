type MemoryPanelProps = {
  notes: string;
  onRefresh: () => void;
};

export function MemoryPanel({ notes, onRefresh }: MemoryPanelProps) {
  return (
    <section className="panel memory-panel" aria-labelledby="memoryTitle">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Memory</p>
          <h2 id="memoryTitle">Recent Notes</h2>
        </div>
        <button className="ghost-button" onClick={onRefresh} type="button">
          Refresh
        </button>
      </div>
      <pre className="memory-log">{notes}</pre>
    </section>
  );
}
