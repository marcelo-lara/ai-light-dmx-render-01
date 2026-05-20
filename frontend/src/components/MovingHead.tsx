import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { MutableRefObject, RefObject } from 'react';
import type { Fixture, FixtureState } from '../hooks/useFixtures';

interface Props {
  fixtureData: Fixture;
  targetRef: RefObject<THREE.Mesh | null>;
  fixtureId: string;
  fixtureStatesRef: MutableRefObject<Record<string, FixtureState>>;
}

export function MovingHead({ fixtureData, targetRef, fixtureId, fixtureStatesRef }: Props) {
  const baseRef = useRef<THREE.Group>(null); // pan  — Y rotation
  const headRef = useRef<THREE.Group>(null); // tilt — X rotation
  const beamMaterialRef = useRef<THREE.MeshBasicMaterial>(null);

  useFrame(() => {
    if (!targetRef.current || !baseRef.current || !headRef.current) return;

    const targetPos = targetRef.current.position;

    // location.x → scene X, location.z → scene Y (height), location.y → scene Z (depth)
    const sceneX = fixtureData.location.x;
    const sceneY = fixtureData.location.z;
    const sceneZ = fixtureData.location.y;

    const dx = targetPos.x - sceneX;
    const dy = targetPos.y - sceneY;
    const dz = targetPos.z - sceneZ;

    // Pan: atan2 of X and Z displacement
    // TODO: clamp to physical fixture pan limits once ranges are confirmed
    const panAngle = THREE.MathUtils.clamp(Math.atan2(dx, dz), -Math.PI, Math.PI);
    baseRef.current.rotation.y = panAngle;

    // Tilt: angle from straight-down (tilt=0 → floor, tilt=π/2 → horizontal, tilt=π → ceiling)
    const distance2D = Math.hypot(dx, dz);
    const tiltAngle = THREE.MathUtils.clamp(
      Math.atan2(distance2D, -dy),
      0,
      Math.PI
    );
    headRef.current.rotation.x = -tiltAngle;

    // Update beam colour and opacity from live fixture state
    const fs = fixtureStatesRef.current[fixtureId];
    if (fs && beamMaterialRef.current) {
      beamMaterialRef.current.color.set(fs.color_hex);
      beamMaterialRef.current.opacity = fs.intensity * 0.6;
    }
  });

  // location.x → scene X, location.z → scene Y (height), location.y → scene Z (depth)
  const { x, y: sceneZ, z: sceneY } = fixtureData.location;

  // Housing orientation: rotated to lie against its wall, or vertical for ceiling.
  // Lives OUTSIDE baseRef so it stays static while pan/tilt operate independently.
  const housingRot: [number, number, number] =
    fixtureData.mount === 'wall_left'  ? [0, 0,          Math.PI / 2] :
    fixtureData.mount === 'wall_right' ? [0, 0,          Math.PI / 2] :
    fixtureData.mount === 'wall_back'  ? [Math.PI / 2, 0, 0         ] :
    [0, 0, 0]; // ceiling: vertical

  // Bracket arm: extends from fixture toward its wall.
  // Length = distance to the wall in scene space.
  const armLen =
    fixtureData.mount === 'wall_left'  ? fixtureData.location.x :
    fixtureData.mount === 'wall_right' ? 1 - fixtureData.location.x :
    fixtureData.mount === 'wall_back'  ? fixtureData.location.y :
    0;
  const bracketArm: { pos: [number, number, number]; rot: [number, number, number] } | null =
    armLen > 0.01
      ? fixtureData.mount === 'wall_left'  ? { pos: [-armLen / 2, 0, 0], rot: [0, 0, Math.PI / 2] }
      : fixtureData.mount === 'wall_right' ? { pos: [ armLen / 2, 0, 0], rot: [0, 0, Math.PI / 2] }
      : fixtureData.mount === 'wall_back'  ? { pos: [0, 0, -armLen / 2], rot: [Math.PI / 2, 0, 0] }
      : null
    : null;

  return (
    <group position={[x, sceneY, sceneZ]}>
      {/* Static housing — oriented against wall, does NOT pan */}
      <mesh rotation={housingRot}>
        <cylinderGeometry args={[0.04, 0.05, 0.08, 12]} />
        <meshStandardMaterial color="#1e1e2e" />
      </mesh>

      {/* Bracket arm from housing to wall (wall-mounts only) */}
      {bracketArm && (
        <mesh position={bracketArm.pos} rotation={bracketArm.rot}>
          <cylinderGeometry args={[0.018, 0.018, armLen, 8]} />
          <meshStandardMaterial color="#2e2e40" />
        </mesh>
      )}

      {/* Pan group — rotates around world Y axis */}
      <group ref={baseRef}>
        {/* Head — tilts around X axis, hangs below pan pivot */}
        <group ref={headRef} position={[0, -0.09, 0]}>
          <mesh>
            <boxGeometry args={[0.07, 0.12, 0.07]} />
            <meshStandardMaterial color="#2a2a3e" />
          </mesh>

          {/* Beam — narrow at lens, expands toward floor */}
          <mesh position={[0, -0.5, 0]}>
            <cylinderGeometry args={[
              0.003,
              Math.tan((fixtureData.beam_angle_degrees / 2) * (Math.PI / 180)),
              1, 8
            ]} />
            <meshBasicMaterial ref={beamMaterialRef} color="#ffffff" transparent opacity={0} />
          </mesh>
        </group>
      </group>
    </group>
  );
}
