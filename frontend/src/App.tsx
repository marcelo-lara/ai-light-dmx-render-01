import { useFixtures } from './hooks/useFixtures';
import { StageCanvas } from './components/StageCanvas';

export function App() {
  const { fixtures, pois, connected, ballPositionRef } = useFixtures();
  const movingHeads = fixtures.filter((f) => f.fixture_type === 'moving_head');
  const parcans = fixtures.filter((f) => f.fixture_type === 'parcan');

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
      <StageCanvas movingHeads={movingHeads} parcans={parcans} pois={pois} ballPositionRef={ballPositionRef} />
    </div>
  );
}
