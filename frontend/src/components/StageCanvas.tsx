import { useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { MutableRefObject } from 'react';
import type { Fixture, FixtureLocation, FixtureState, POI } from '../hooks/useFixtures';
import { BoundingBox } from './BoundingBox';
import { BouncingBall } from './BouncingBall';
import { MovingHead } from './MovingHead';
import { ParCan } from './ParCan';
import { POIMarker } from './POIMarker';

interface Props {
  movingHeads: Fixture[];
  parcans: Fixture[];
  pois: POI[];
  ballPositionRef: MutableRefObject<FixtureLocation>;
  fixtureStatesRef: MutableRefObject<Record<string, FixtureState>>;
}

export function StageCanvas({ movingHeads, parcans, pois, ballPositionRef, fixtureStatesRef }: Props) {
  const ballRef = useRef<THREE.Mesh>(null);

  return (
    <Canvas
      camera={{ position: [1.8, 1.2, 2.2], fov: 50 }}
      style={{ width: '100%', height: '100%' }}
    >
      <color attach="background" args={['#0a0a0f']} />
      <ambientLight intensity={0.4} />
      <pointLight position={[0.5, 1.5, 0.5]} intensity={0.6} />

      <OrbitControls target={[0.5, 0.5, 0.5]} />

      <gridHelper
        args={[1, 10, '#333355', '#1e1e33']}
        position={[0.5, 0, 0.5]}
      />

      <BoundingBox />
      <BouncingBall meshRef={ballRef} ballPositionRef={ballPositionRef} />

      {pois
        .filter((p) => !p.id.startsWith('ref_'))
        .map((p) => (
          <POIMarker key={p.id} poi={p} />
        ))}

      {parcans.map((f) => (
        <ParCan
          key={f.id}
          fixtureData={f}
          fixtureId={f.id}
          fixtureStatesRef={fixtureStatesRef}
        />
      ))}

      {movingHeads.map((f) => (
        <MovingHead
          key={f.id}
          fixtureData={f}
          fixtureId={f.id}
          targetRef={ballRef}
          fixtureStatesRef={fixtureStatesRef}
        />
      ))}
    </Canvas>
  );
}
