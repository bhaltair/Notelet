export type RuntimeEvent =
  | { type: "user_message"; content: string }
  | { type: "answer_delta"; content: string }
  | {
      type: "model_response";
      model: string;
      content: string | null;
      tool_call_count: number;
    }
  | {
      type: "tool_call";
      name: string;
      arguments: Record<string, unknown>;
    }
  | {
      type: "tool_result";
      name: string;
      output: string;
      is_error: boolean;
    }
  | { type: "tool_error"; name: string; message: string }
  | { type: "final_answer"; content: string }
  | { type: "error"; message: string };

export type ChatMessage = {
  id: string;
  role: "user" | "agent";
  content: string;
};

export type HealthPayload = {
  ok: boolean;
  model: string;
};

export type NotesPayload = {
  notes: string;
};
