import { useFixtures } from './hooks/useFixtures';
import { StageCanvas } from './components/StageCanvas';
import { Sidebar } from './components/Sidebar';

export function App() {
  const {
    fixtures,
    pois,
    connected,
    simMode,
    activePoiId,
    setSimMode,
    ballSpeed,
    setBallSpeed,
    dmxOutputEnabled,
    setDmxOutputEnabled,
    ballPositionRef,
    fixtureStatesRef,
    sendFixtureCommand,
  } = useFixtures();
  const movingHeads = fixtures.filter((f) => f.fixture_type === 'moving_head');
  const parcans = fixtures.filter((f) => f.fixture_type === 'parcan');

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden' }}>
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
      <div style={{ flex: 1, minWidth: 0 }}>
        <StageCanvas movingHeads={movingHeads} parcans={parcans} pois={pois} activePoiId={activePoiId} ballPositionRef={ballPositionRef} fixtureStatesRef={fixtureStatesRef} />
      </div>
      <Sidebar
        movingHeads={movingHeads}
        parcans={parcans}
        simMode={simMode}
        activePoiId={activePoiId}
        setSimMode={setSimMode}
        ballSpeed={ballSpeed}
        setBallSpeed={setBallSpeed}
        dmxOutputEnabled={dmxOutputEnabled}
        setDmxOutputEnabled={setDmxOutputEnabled}
        sendFixtureCommand={sendFixtureCommand}
      />
    </div>
  );
}
