import { useFixtures } from './hooks/useFixtures';
import { StageCanvas } from './components/StageCanvas';

export function App() {
  const { fixtures, connected, ballPositionRef } = useFixtures();
  const movingHeads = fixtures.filter((f) => f.fixture.includes('moving_head'));

  return (
    <div style={{ width: '100vw', height: '100vh' }}>
      {!connected && (
        <div
          style={{
            position: 'absolute',
            top: 16,
            left: 16,
            zIndex: 10,
            color: '#ff6680',
            fontSize: 11,
            fontFamily: 'monospace',
            pointerEvents: 'none',
          }}
        >
          connecting to backend…
        </div>
      )}
      <StageCanvas fixtures={movingHeads} ballPositionRef={ballPositionRef} />
    </div>
  );
}
