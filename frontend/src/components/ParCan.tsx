import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { MutableRefObject } from 'react';
import type { Fixture, FixtureState } from '../hooks/useFixtures';

interface Props {
  fixtureData: Fixture;
  fixtureId: string;
  fixtureStatesRef: MutableRefObject<Record<string, FixtureState>>;
}

/**
 * Static ceiling-mounted wash light.
 *
 * Mounted at y=1 (ceiling) using location.x and location.z for horizontal
 * placement. The beam is a downward cone — narrow at the lens, wide at the
 * floor — spanning the full unit-cube height.
 */
export function ParCan({ fixtureData, fixtureId, fixtureStatesRef }: Props) {
  // location.x → scene X, location.z → scene Y (mounting height), location.y → scene Z (depth)
  const { x, y: sceneZ, z: mountHeight } = fixtureData.location;
  const beamMaterialRef = useRef<THREE.MeshBasicMaterial>(null);

  useFrame(() => {
    const fs = fixtureStatesRef.current[fixtureId];
    if (fs && beamMaterialRef.current) {
      beamMaterialRef.current.color.set(fs.color_hex);
      beamMaterialRef.current.opacity = fs.intensity * 0.4;
    }
  });

  return (
    <group position={[x, mountHeight, sceneZ]}>
      {/* Housing */}
      <mesh>
        <cylinderGeometry args={[0.04, 0.04, 0.06, 12]} />
        <meshStandardMaterial color="#1e1e2e" />
      </mesh>

      {/*
       * Beam: spans from mounting height down to the floor (y=0 in world space).
       * Cylinder center is offset by -mountHeight/2 so the top sits at the fixture
       * and the bottom reaches the floor.
       */}
      <mesh position={[0, -mountHeight / 2, 0]}>
        <cylinderGeometry args={[
          0.025,
          mountHeight * Math.tan((fixtureData.beam_angle_degrees / 2) * (Math.PI / 180)),
          mountHeight, 10
        ]} />
        <meshBasicMaterial ref={beamMaterialRef} color="#000000" transparent opacity={0} />
      </mesh>
    </group>
  );
}
