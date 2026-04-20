import { FormEvent, useState } from "react";

type ComposerProps = {
  disabled: boolean;
  onSend: (message: string) => void;
};

const examples = [
  "Remember: review the React runtime console tomorrow",
  "What notes have I saved?",
  "Search notes for runtime",
];

export function Composer({ disabled, onSend }: ComposerProps) {
  const [message, setMessage] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed) {
      return;
    }
    onSend(trimmed);
    setMessage("");
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <div className="example-row" aria-label="Example prompts">
        {examples.map((example) => (
          <button
            className="example-chip"
            disabled={disabled}
            key={example}
            onClick={() => setMessage(example)}
            type="button"
          >
            {example}
          </button>
        ))}
      </div>
      <div className="composer-row">
        <textarea
          disabled={disabled}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="Remember: review the streaming UI tomorrow"
          required
          rows={3}
          value={message}
        />
        <button disabled={disabled} type="submit">
          Send
        </button>
      </div>
    </form>
  );
}
