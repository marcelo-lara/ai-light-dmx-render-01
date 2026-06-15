import { useState, useEffect, useRef, useCallback } from 'react';
import type { MutableRefObject } from 'react';

export type FixtureType = 'moving_head' | 'parcan';
export type SimMode = '3d' | 'floor' | 'poi';

export interface FixtureLocation {
  x: number;
  y: number;
  z: number;
}

export type MountType = 'wall_left' | 'wall_right' | 'wall_back' | 'ceiling';

/** Live colour + intensity for a single fixture, updated every frame. */
export interface FixtureState {
  color_hex: string;   // e.g. "#FF0000"
  intensity: number;   // 0.0–1.0
}

export interface Fixture {
  id: string;
  name: string;
  fixture: string;          // template ref, e.g. "fixture.moving_head.mini_beam_prism"
  fixture_type: FixtureType; // discriminator from backend fixture model
  base_channel: number;
  channel_count: number;
  absolute_channels: Record<string, number>;
  location: FixtureLocation;
  mount?: MountType;
  beam_angle_degrees: number;
  color_hex: string;
  intensity: number;
  /** Moving-head only: colour-wheel labels in wheel order. */
  color_wheel_options?: string[];
  /** Moving-head only: currently selected colour-wheel label. */
  color_wheel_current?: string;
  /** Moving-head only: current 16-bit pan DMX value. */
  pan?: number;
  /** Moving-head only: current 16-bit tilt DMX value. */
  tilt?: number;
}

export interface POI {
  id: string;
  name: string;
  location: FixtureLocation;
  fixtures: Record<string, { pan: number; tilt: number }>;
  virtual?: boolean;
}

interface FixturesState {
  fixtures: Fixture[];
  pois: POI[];
  connected: boolean;
  simMode: SimMode;
  ballSpeed: number;
  automationEnabled: boolean;
  dmxOutputEnabled: boolean;
  activePoiId: string | null;
  setSimMode: (mode: SimMode) => void;
  setBallSpeed: (speed: number) => void;
  setAutomationEnabled: (enabled: boolean) => void;
  setDmxOutputEnabled: (enabled: boolean) => void;
  applyFixtureTargets: (targets: POI['fixtures']) => void;
  aimAtLocation: (location: FixtureLocation) => void;
  persistPoiTargets: (poiId: string, targets: POI['fixtures']) => void;
  ballPositionRef: MutableRefObject<FixtureLocation>;
  fixtureStatesRef: MutableRefObject<Record<string, FixtureState>>;
  sendFixtureCommand: (id: string, metaKey: string, value: string | number | number[]) => void;
}

export function useFixtures(): FixturesState {
  const [state, setState] = useState<Omit<FixturesState, 'ballPositionRef' | 'fixtureStatesRef' | 'sendFixtureCommand' | 'setSimMode' | 'setBallSpeed' | 'setAutomationEnabled' | 'setDmxOutputEnabled' | 'applyFixtureTargets' | 'aimAtLocation' | 'persistPoiTargets'>>({
    fixtures: [],
    pois: [],
    connected: false,
    simMode: '3d',
    ballSpeed: 1,
    automationEnabled: true,
    dmxOutputEnabled: false,
    activePoiId: null,
  });

  const ballPositionRef = useRef<FixtureLocation>({ x: 0.5, y: 0.5, z: 0.5 });
  const fixtureStatesRef = useRef<Record<string, FixtureState>>({});
  const wsRef = useRef<WebSocket | null>(null);

  const sendFixtureCommand = useCallback(
    (id: string, metaKey: string, value: string | number | number[]) => {
      if (metaKey === 'pan' || metaKey === 'tilt') {
        setState((s) => ({
          ...s,
          fixtures: s.fixtures.map((fixture) => (
            fixture.id === id
              ? { ...fixture, [metaKey]: Number(value) }
              : fixture
          )),
        }));
      }
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'set_fixture', id, meta_key: metaKey, value }));
      }
    },
    []
  );

  const setSimMode = useCallback((mode: SimMode) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'set_sim_mode', mode }));
      setState((s) => ({ ...s, simMode: mode }));
    }
  }, []);

  const setBallSpeed = useCallback((speed: number) => {
    const nextSpeed = Math.max(0.1, Math.min(4, speed));
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'set_ball_speed', speed: nextSpeed }));
      setState((s) => ({ ...s, ballSpeed: nextSpeed }));
    }
  }, []);

  const setAutomationEnabled = useCallback((enabled: boolean) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'set_automation_enabled', enabled }));
      setState((s) => ({ ...s, automationEnabled: enabled }));
    }
  }, []);

  const setDmxOutputEnabled = useCallback((enabled: boolean) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'set_dmx_output', enabled }));
      setState((s) => ({ ...s, dmxOutputEnabled: enabled }));
    }
  }, []);

  const applyFixtureTargets = useCallback((targets: POI['fixtures']) => {
    setState((s) => ({
      ...s,
      fixtures: s.fixtures.map((fixture) => {
        const target = targets[fixture.id];
        if (!target) {
          return fixture;
        }
        return {
          ...fixture,
          pan: target.pan,
          tilt: target.tilt,
        };
      }),
    }));

    for (const [fixtureId, target] of Object.entries(targets)) {
      sendFixtureCommand(fixtureId, 'pan', target.pan);
      sendFixtureCommand(fixtureId, 'tilt', target.tilt);
    }
  }, [sendFixtureCommand]);

  const aimAtLocation = useCallback((location: FixtureLocation) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'aim_at_location', location }));
      ballPositionRef.current = location;
      setState((s) => ({
        ...s,
        automationEnabled: false,
      }));
    }
  }, []);

  const persistPoiTargets = useCallback((poiId: string, targets: POI['fixtures']) => {
    setState((s) => ({
      ...s,
      pois: s.pois.map((poi) => (
        poi.id === poiId
          ? {
              ...poi,
              fixtures: {
                ...poi.fixtures,
                ...targets,
              },
            }
          : poi
      )),
    }));

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'save_poi_targets', poi_id: poiId, fixture_targets: targets }));
    }
  }, []);

  useEffect(() => {
    const wsUrl = `ws://${window.location.hostname}:5141/ws`;
    let ws: WebSocket;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => setState((s) => ({ ...s, connected: true }));

      ws.onmessage = (e: MessageEvent<string>) => {
        const msg = JSON.parse(e.data) as {
          type: string;
          fixtures?: Fixture[];
          pois?: POI[];
          ball?: FixtureLocation;
          fixture_states?: Record<string, FixtureState>;
          sim_mode?: SimMode;
          ball_speed?: number;
          automation_enabled?: boolean;
          dmx_output_enabled?: boolean;
          active_poi_id?: string | null;
        };
        if (msg.type === 'init' && msg.fixtures && msg.pois) {
          const fixtures = msg.fixtures;
          const pois = msg.pois;

          // Seed fixtureStatesRef from init payload (no re-render needed)
          const initial: Record<string, FixtureState> = {};
          for (const f of fixtures) {
            initial[f.id] = { color_hex: f.color_hex, intensity: f.intensity };
          }
          fixtureStatesRef.current = initial;
          setState((s) => ({
            ...s,
            fixtures,
            pois,
            connected: true,
            simMode: msg.sim_mode ?? s.simMode,
            ballSpeed: msg.ball_speed ?? s.ballSpeed,
            automationEnabled: msg.automation_enabled ?? s.automationEnabled,
            dmxOutputEnabled: msg.dmx_output_enabled ?? s.dmxOutputEnabled,
            activePoiId: msg.active_poi_id ?? s.activePoiId,
          }));
        } else if (msg.type === 'settings') {
          setState((s) => ({
            ...s,
            simMode: msg.sim_mode ?? s.simMode,
            ballSpeed: msg.ball_speed ?? s.ballSpeed,
            automationEnabled: msg.automation_enabled ?? s.automationEnabled,
            dmxOutputEnabled: msg.dmx_output_enabled ?? s.dmxOutputEnabled,
            activePoiId: msg.active_poi_id ?? s.activePoiId,
          }));
        } else if (msg.type === 'pois_updated' && msg.pois) {
          setState((s) => ({
            ...s,
            pois: msg.pois ?? s.pois,
          }));
        } else if (msg.type === 'frame') {
          // Update refs without triggering a re-render
          if (msg.ball) {
            ballPositionRef.current = msg.ball;
          }
          if (msg.fixture_states) {
            Object.assign(fixtureStatesRef.current, msg.fixture_states);
          }
          if (msg.active_poi_id !== undefined) {
            setState((s) => {
              const nextActivePoiId = msg.active_poi_id ?? null;
              if (s.activePoiId === nextActivePoiId) {
                return s;
              }
              return { ...s, activePoiId: nextActivePoiId };
            });
          }
        }
      };

      ws.onclose = () => {
        wsRef.current = null;
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

  return { ...state, ballPositionRef, fixtureStatesRef, sendFixtureCommand, setSimMode, setBallSpeed, setAutomationEnabled, setDmxOutputEnabled, applyFixtureTargets, aimAtLocation, persistPoiTargets };
}

