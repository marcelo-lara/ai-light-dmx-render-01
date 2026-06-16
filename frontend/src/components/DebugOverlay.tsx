import { useEffect, useState } from 'react';
import type { MutableRefObject } from 'react';
import type { Fixture, FixtureState } from '../hooks/useFixtures';
import { getBeamOpacity } from './beamVisuals';

interface Props {
  movingHeads: Fixture[];
  fixtureStatesRef: MutableRefObject<Record<string, FixtureState>>;
}

const S = {
  panel: {
    position: 'absolute' as const,
    top: 16,
    left: 16,
    zIndex: 12,
    width: 340,
    maxHeight: 'calc(100vh - 32px)',
    overflowY: 'auto' as const,
    padding: '10px 12px',
    border: '1px solid rgba(120, 140, 255, 0.22)',
    borderRadius: 8,
    background: 'rgba(8, 10, 18, 0.82)',
    backdropFilter: 'blur(10px)',
    color: '#cbd2ff',
    fontFamily: 'monospace',
    fontSize: 11,
    pointerEvents: 'none' as const,
  },
  title: {
    marginBottom: 8,
    color: '#eef1ff',
    letterSpacing: '0.08em',
    textTransform: 'uppercase' as const,
    fontSize: 10,
  },
  fixture: {
    padding: '8px 0',
    borderTop: '1px solid rgba(90, 100, 150, 0.2)',
  },
  name: {
    color: '#ffffff',
    marginBottom: 4,
  },
  line: {
    color: '#aeb7ea',
    lineHeight: 1.45,
  },
  subtle: {
    color: '#7f89b8',
  },
};

function radToDeg(value: number): string {
  return `${(value * 180 / Math.PI).toFixed(1)} deg`;
}

export function DebugOverlay({ movingHeads, fixtureStatesRef }: Props) {
  const [, setTick] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setTick((value) => (value + 1) % 100000);
    }, 120);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div style={S.panel}>
      <div style={S.title}>Moving Head Debug</div>
      {movingHeads.map((fixture) => {
        const live = fixtureStatesRef.current[fixture.id] ?? {
          color_hex: fixture.color_hex,
          intensity: fixture.intensity,
          pan: fixture.pan,
          tilt: fixture.tilt,
        };
        const beamOpacity = getBeamOpacity(live.color_hex, live.intensity, 0.6);
        return (
          <div key={fixture.id} style={S.fixture}>
            <div style={S.name}>{fixture.name}</div>
            <div style={S.line}>pan: {live.pan ?? fixture.pan ?? 0} | tilt: {live.tilt ?? fixture.tilt ?? 0}</div>
            <div style={S.line}>dim: {(live.intensity * 100).toFixed(1)}% | beam opacity: {beamOpacity.toFixed(3)}</div>
            <div style={S.line}>color: {live.color_hex}</div>
            {fixture.orientation ? (
              <>
                <div style={S.line}>yaw: {radToDeg(fixture.orientation.yaw)} | pitch: {radToDeg(fixture.orientation.pitch)}</div>
                <div style={S.line}>roll: {radToDeg(fixture.orientation.roll)} | pan_sign: {fixture.orientation.pan_sign > 0 ? '+1' : '-1'}</div>
                <div style={S.line}>tilt_reversed: {String(fixture.orientation.tilt_reversed)}</div>
              </>
            ) : (
              <div style={{ ...S.line, ...S.subtle }}>orientation: none</div>
            )}
          </div>
        );
      })}
    </div>
  );
}