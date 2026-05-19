import { useState, useEffect } from 'react';

export interface FixtureLocation {
  x: number;
  y: number;
  z: number;
}

export interface Fixture {
  id: string;
  name: string;
  fixture: string;
  base_channel: number;
  location: FixtureLocation;
}

export interface POI {
  id: string;
  name: string;
  location: FixtureLocation;
  fixtures: Record<string, { pan: number; tilt: number }>;
}

interface FixturesState {
  fixtures: Fixture[];
  pois: POI[];
  connected: boolean;
}

export function useFixtures(): FixturesState {
  const [state, setState] = useState<FixturesState>({
    fixtures: [],
    pois: [],
    connected: false,
  });

  useEffect(() => {
    const wsUrl = `ws://${window.location.host}/ws`;
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      ws = new WebSocket(wsUrl);

      ws.onopen = () => setState((s) => ({ ...s, connected: true }));

      ws.onmessage = (e: MessageEvent<string>) => {
        const msg = JSON.parse(e.data) as { type: string; fixtures?: Fixture[]; pois?: POI[] };
        if (msg.type === 'init' && msg.fixtures && msg.pois) {
          setState({ fixtures: msg.fixtures, pois: msg.pois, connected: true });
        }
      };

      ws.onclose = () => {
        setState((s) => ({ ...s, connected: false }));
        reconnectTimer = setTimeout(connect, 3000);
      };

      ws.onerror = () => ws.close();
    }

    connect();

    return () => {
      clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, []);

  return state;
}
