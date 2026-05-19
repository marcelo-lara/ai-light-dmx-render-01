import { useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';
import type { MutableRefObject } from 'react';
import type { Fixture, FixtureLocation } from '../hooks/useFixtures';
import { BoundingBox } from './BoundingBox';
import { BouncingBall } from './BouncingBall';
import { MovingHead } from './MovingHead';

const BEAM_COLORS = ['#4488ff', '#ff6680', '#44dd88'];

interface Props {
  fixtures: Fixture[];
  ballPositionRef: MutableRefObject<FixtureLocation>;
}

export function StageCanvas({ fixtures, ballPositionRef }: Props) {
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

      {fixtures.map((f, i) => (
        <MovingHead
          key={f.id}
          fixtureData={f}
          targetRef={ballRef}
          color={BEAM_COLORS[i % BEAM_COLORS.length]}
        />
      ))}
    </Canvas>
  );
}
