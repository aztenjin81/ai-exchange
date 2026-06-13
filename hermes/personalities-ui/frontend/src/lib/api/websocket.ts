import { WsEvent } from '$lib/types';

type EventHandler = (event: WsEvent) => void;

const WS_BASE = import.meta.env.PUBLIC_WS_URL || 'ws://localhost:8000';

export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private handlers = new Map<string, EventHandler[]>();
  private personalityId: string;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(personalityId: string) {
    this.personalityId = personalityId;
  }

  connect() {
    this.ws = new WebSocket(`${WS_BASE}/ws/${this.personalityId}`);

    this.ws.onopen = () => {
      console.log(`WS connected: ${this.personalityId}`);
      this.reconnectTimer = null;
    };

    this.ws.onmessage = (msg) => {
      try {
        const event: WsEvent = JSON.parse(msg.data);
        const typeHandlers = this.handlers.get(event.type) || [];
        typeHandlers.forEach((fn) => fn(event));
        // Also fire catch-all handlers
        const allHandlers = this.handlers.get('*') || [];
        allHandlers.forEach((fn) => fn(event));
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    this.ws.onclose = () => {
      if (!this.reconnectTimer) {
        this.reconnectTimer = setTimeout(() => this.connect(), 3000);
      }
    };

    this.ws.onerror = () => {
      this.ws?.close();
    };
  }

  send(text: string) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: 'chat', content: text }));
    }
  }

  on(eventType: string, handler: EventHandler) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, []);
    }
    this.handlers.get(eventType)!.push(handler);
  }

  off(eventType: string, handler: EventHandler) {
    const list = this.handlers.get(eventType);
    if (list) {
      const idx = list.indexOf(handler);
      if (idx >= 0) list.splice(idx, 1);
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}
