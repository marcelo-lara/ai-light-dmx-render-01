import type { Fixture } from '../hooks/useFixtures';

interface Props {
  fixtureData: Fixture;
  color: string;
}

/**
 * Static ceiling-mounted wash light.
 *
 * Mounted at y=1 (ceiling) using location.x and location.z for horizontal
 * placement. The beam is a downward cone — narrow at the lens, wide at the
 * floor — spanning the full unit-cube height.
 */
export function ParCan({ fixtureData, color }: Props) {
  // location.x → scene X, location.z → scene Y (mounting height), location.y → scene Z (depth)
  const { x, y: sceneZ, z: mountHeight } = fixtureData.location;

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
        <meshBasicMaterial color={color} transparent opacity={0.4} />
      </mesh>
    </group>
  );
}
