import { useState } from 'react';
import { useFixtures } from './hooks/useFixtures';
import { StageCanvas } from './components/StageCanvas';
import { Sidebar } from './components/Sidebar';
import type { FixtureLocation, POI } from './hooks/useFixtures';

export function App() {
  const [showPois, setShowPois] = useState(true);
  const [showRefs, setShowRefs] = useState(false);
  const [selectedPoiId, setSelectedPoiId] = useState<string | null>(null);
  const [targetLocation, setTargetLocation] = useState<FixtureLocation | null>(null);
  const {
    fixtures,
    pois,
    connected,
    simMode,
    activePoiId,
    setSimMode,
    ballSpeed,
    setBallSpeed,
    automationEnabled,
    setAutomationEnabled,
    dmxOutputEnabled,
    setDmxOutputEnabled,
    applyFixtureTargets,
    persistPoiTargets,
    ballPositionRef,
    fixtureStatesRef,
    sendFixtureCommand,
  } = useFixtures();
  const movingHeads = fixtures.filter((f) => f.fixture_type === 'moving_head');
  const parcans = fixtures.filter((f) => f.fixture_type === 'parcan');
  const selectedPoi = selectedPoiId ? pois.find((poi) => poi.id === selectedPoiId) ?? null : null;
  const selectedTargetLabel = selectedPoi ? `${selectedPoi.name} (${selectedPoi.id})` : null;
  const selectedTargetDirty = selectedPoi
    ? movingHeads.some((fixture) => {
        const target = selectedPoi.fixtures[fixture.id];
        return !!target && (target.pan !== (fixture.pan ?? 0) || target.tilt !== (fixture.tilt ?? 0));
      })
    : false;

  function handleAutomationEnabled(enabled: boolean) {
    setAutomationEnabled(enabled);
    if (enabled) {
      setSelectedPoiId(null);
      setTargetLocation(null);
    }
  }

  function handleSelectPoi(poi: POI) {
    handleAutomationEnabled(false);
    setSelectedPoiId(poi.id);
    setTargetLocation(poi.location);
    applyFixtureTargets(poi.fixtures);
  }

  function handlePersistSelectedTarget() {
    if (!selectedPoi) {
      return;
    }

    const targets = Object.fromEntries(
      movingHeads.map((fixture) => [
        fixture.id,
        {
          pan: fixture.pan ?? 0,
          tilt: fixture.tilt ?? 0,
        },
      ])
    );

    persistPoiTargets(selectedPoi.id, targets);
  }

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
        <StageCanvas movingHeads={movingHeads} parcans={parcans} pois={pois} activePoiId={selectedPoiId ?? activePoiId} showPois={showPois} showRefs={showRefs} targetLocation={targetLocation} onSelectPoi={handleSelectPoi} ballPositionRef={ballPositionRef} fixtureStatesRef={fixtureStatesRef} />
      </div>
      <Sidebar
        movingHeads={movingHeads}
        parcans={parcans}
        simMode={simMode}
        activePoiId={activePoiId}
        selectedTargetLabel={selectedTargetLabel}
        selectedTargetDirty={selectedTargetDirty}
        persistSelectedTarget={handlePersistSelectedTarget}
        showPois={showPois}
        setShowPois={setShowPois}
        showRefs={showRefs}
        setShowRefs={setShowRefs}
        setSimMode={setSimMode}
        ballSpeed={ballSpeed}
        setBallSpeed={setBallSpeed}
        automationEnabled={automationEnabled}
        setAutomationEnabled={handleAutomationEnabled}
        dmxOutputEnabled={dmxOutputEnabled}
        setDmxOutputEnabled={setDmxOutputEnabled}
        sendFixtureCommand={sendFixtureCommand}
      />
    </div>
  );
}
