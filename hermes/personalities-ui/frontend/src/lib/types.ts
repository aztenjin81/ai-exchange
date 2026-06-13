export interface Personality {
  id: string;
  name: string;
  system_prompt: string;
  model: string;
  provider_id: string;
  avatar: string;
  token_budget_total: number;
  token_budget_cost: number;
  mcp_server_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface PersonalityCreate {
  name: string;
  system_prompt?: string;
  model?: string;
  provider_id?: string;
  avatar?: string;
  token_budget_total?: number;
  token_budget_cost?: number;
}

export interface Provider {
  id: string;
  name: string;
  type: 'openai' | 'anthropic' | 'openrouter' | 'ollama' | 'vllm' | 'custom';
  base_url: string;
  models: string[];
  note: string;
  created_at: string;
  updated_at: string;
}

export interface McpServer {
  id: string;
  name: string;
  transport: 'stdio' | 'http';
  command: string;
  args: string[];
  env: Record<string, string>;
  url: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CronJob {
  id: string;
  name: string;
  schedule: string;
  personality_id: string;
  prompt: string;
  skills: string[];
  no_agent: boolean;
  script_path: string;
  enabled: boolean;
  delivery_target: string;
  model_override: string;
  workdir: string;
  created_at: string;
  updated_at: string;
}

export interface Workflow {
  id: string;
  name: string;
  enabled: boolean;
  steps: WorkflowStep[];
  created_at: string;
  updated_at: string;
}

export interface WorkflowStep {
  id?: number;
  workflow_id?: string;
  step_order: number;
  job_id: string;
  depends_on: string;
  condition: string;
  on_success: string;
  on_failure: string;
}

export interface Session {
  id: string;
  personality_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  session_id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  tool_calls: ToolCall[];
  tokens_in: number;
  tokens_out: number;
  cost: number;
  created_at: string;
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: string;
  status?: 'running' | 'success' | 'error';
}

// WebSocket event types
export type WsEvent =
  | { type: 'thinking'; content: string }
  | { type: 'tool_call'; tool_call_id: string; name: string; arguments: string }
  | { type: 'tool_result'; tool_call_id: string; result: string }
  | { type: 'response'; content: string }
  | { type: 'usage'; tokens_in: number; tokens_out: number; cost: number }
  | { type: 'error'; message: string }
  | { type: 'done' };
