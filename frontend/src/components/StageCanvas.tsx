import { useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { MutableRefObject } from 'react';
import type { Fixture, FixtureLocation, POI } from '../hooks/useFixtures';
import { BoundingBox } from './BoundingBox';
import { BouncingBall } from './BouncingBall';
import { MovingHead } from './MovingHead';
import { ParCan } from './ParCan';
import { POIMarker } from './POIMarker';

const MOVING_HEAD_COLORS = ['#4488ff', '#ff6680', '#44dd88'];
const PARCAN_COLORS = ['#ff6644', '#ff44aa', '#44aaff', '#88ff44'];

interface Props {
  movingHeads: Fixture[];
  parcans: Fixture[];
  pois: POI[];
  ballPositionRef: MutableRefObject<FixtureLocation>;
}

export function StageCanvas({ movingHeads, parcans, pois, ballPositionRef }: Props) {
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

      {parcans.map((f, i) => (
        <ParCan
          key={f.id}
          fixtureData={f}
          color={PARCAN_COLORS[i % PARCAN_COLORS.length]}
        />
      ))}

      {movingHeads.map((f, i) => (
        <MovingHead
          key={f.id}
          fixtureData={f}
          targetRef={ballRef}
          color={MOVING_HEAD_COLORS[i % MOVING_HEAD_COLORS.length]}
        />
      ))}
    </Canvas>
  );
}
