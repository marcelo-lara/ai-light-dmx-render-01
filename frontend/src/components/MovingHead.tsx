import { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { MutableRefObject, RefObject } from 'react';
import type { Fixture, FixtureState } from '../hooks/useFixtures';
import { getBeamOpacity } from './beamVisuals';

const DMX_MAX = 65535;
const PAN_RANGE_RADIANS = THREE.MathUtils.degToRad(540);
const TILT_RANGE_RADIANS = THREE.MathUtils.degToRad(270);

function canonicalDirectionFromDmx(
  pan: number,
  tilt: number,
  panSign: number,
  tiltReversed: boolean
): THREE.Vector3 {
  const basePan = (pan / DMX_MAX) * PAN_RANGE_RADIANS;
  const baseTilt = (tilt / DMX_MAX) * TILT_RANGE_RADIANS;
  const panRadians = panSign * basePan;
  const tiltRadians = tiltReversed ? TILT_RANGE_RADIANS - baseTilt : baseTilt;
  const horizontal = Math.sin(tiltRadians);
  return new THREE.Vector3(
    horizontal * Math.cos(panRadians),
    horizontal * Math.sin(panRadians),
    Math.cos(tiltRadians)
  ).normalize();
}

function worldDirectionFromFixture(fixtureData: Fixture): THREE.Vector3 | null {
  const orientation = fixtureData.orientation;
  if (!orientation || fixtureData.pan === undefined || fixtureData.tilt === undefined) {
    return null;
  }

  const canonical = canonicalDirectionFromDmx(
    fixtureData.pan,
    fixtureData.tilt,
    orientation.pan_sign,
    orientation.tilt_reversed
  );
  const euler = new THREE.Euler(
    orientation.roll,
    orientation.pitch,
    orientation.yaw,
    'XYZ'
  );
  return canonical.applyEuler(euler).normalize();
}

function directionToScene(direction: THREE.Vector3): THREE.Vector3 {
  return new THREE.Vector3(direction.x, direction.z, direction.y).normalize();
}

interface Props {
  fixtureData: Fixture;
  targetRef: RefObject<THREE.Mesh | null>;
  fixtureId: string;
  fixtureStatesRef: MutableRefObject<Record<string, FixtureState>>;
}

export function MovingHead({ fixtureData, targetRef, fixtureId, fixtureStatesRef }: Props) {
  const baseRef = useRef<THREE.Group>(null); // pan  — Y rotation
  const headRef = useRef<THREE.Group>(null); // tilt — X rotation
  const beamRef = useRef<THREE.Mesh>(null);
  const beamMaterialRef = useRef<THREE.MeshBasicMaterial>(null);

  const sceneBounds = new THREE.Box3(
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(1, 1, 1)
  );
  const fallbackDirection = new THREE.Vector3();
  const beamOrigin = new THREE.Vector3();
  const beamDirection = new THREE.Vector3(0, -1, 0);
  const beamQuaternion = new THREE.Quaternion();
  const beamProbeOrigin = new THREE.Vector3();

  useFrame(() => {
    if (!baseRef.current || !headRef.current) return;

    const liveState = fixtureStatesRef.current[fixtureId];
    const fixtureForAim = {
      ...fixtureData,
      pan: liveState?.pan ?? fixtureData.pan,
      tilt: liveState?.tilt ?? fixtureData.tilt,
    };
    const worldDirection = worldDirectionFromFixture(fixtureForAim);

    // location.x → scene X, location.z → scene Y (height), location.y → scene Z (depth)
    const sceneX = fixtureData.location.x;
    const sceneY = fixtureData.location.z;
    const sceneZ = fixtureData.location.y;

    let dx: number;
    let dy: number;
    let dz: number;
    if (worldDirection) {
      const sceneDirection = directionToScene(worldDirection);
      dx = sceneDirection.x;
      dy = sceneDirection.y;
      dz = sceneDirection.z;
    } else {
      if (!targetRef.current) {
        return;
      }
      const targetPos = targetRef.current.position;
      fallbackDirection.set(targetPos.x - sceneX, targetPos.y - sceneY, targetPos.z - sceneZ).normalize();
      dx = fallbackDirection.x;
      dy = fallbackDirection.y;
      dz = fallbackDirection.z;
    }

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

    if (beamRef.current) {
      headRef.current.getWorldPosition(beamOrigin);
      headRef.current.getWorldQuaternion(beamQuaternion);
      beamDirection.set(0, -1, 0);
      beamDirection.applyQuaternion(beamQuaternion).normalize();

      // Wall-mounted heads can sit exactly on the room boundary; probe a hair
      // forward so the box intersection returns the exit point, not the origin.
      beamProbeOrigin.copy(beamOrigin).addScaledVector(beamDirection, 1e-4);

      const beamHit = new THREE.Ray(beamProbeOrigin, beamDirection).intersectBox(sceneBounds, new THREE.Vector3());
      const beamLength = beamHit ? Math.max(beamOrigin.distanceTo(beamHit), 0.001) : 0.001;

      beamRef.current.position.set(0, -beamLength / 2, 0);
      beamRef.current.scale.set(beamLength, beamLength, beamLength);
    }

    // Update beam colour and opacity from live fixture state
    const fs = liveState;
    if (fs && beamMaterialRef.current) {
      beamMaterialRef.current.color.set(fs.color_hex);
      beamMaterialRef.current.opacity = getBeamOpacity(fs.color_hex, fs.intensity, 0.6);
      if (beamRef.current) {
        beamRef.current.visible = beamMaterialRef.current.opacity > 0.001;
      }
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
          <mesh ref={beamRef} position={[0, -0.5, 0]}>
            <cylinderGeometry args={[
              0.003,
              Math.tan((fixtureData.beam_angle_degrees / 2) * (Math.PI / 180)),
              1, 8
            ]} />
            <meshBasicMaterial ref={beamMaterialRef} color="#ffffff" transparent opacity={0} depthWrite={false} />
          </mesh>
        </group>
      </group>
    </group>
  );
}
