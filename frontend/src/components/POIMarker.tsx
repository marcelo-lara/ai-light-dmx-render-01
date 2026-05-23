import { Text } from '@react-three/drei';
import type { POI } from '../hooks/useFixtures';

interface Props {
  poi: POI;
  active: boolean;
}

export function POIMarker({ poi, active }: Props) {
  const { x, y: sceneZ, z: sceneY } = poi.location;
  const color = active ? '#7df2a7' : '#ffdd44';
  const size = active ? 0.036 : 0.025;

  return (
    <group position={[x, sceneY, sceneZ]}>
      <mesh>
        <boxGeometry args={[size, size, size]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={active ? 1 : 0.6} />
      </mesh>
      <Text
        position={[0, 0.04, 0]}
        fontSize={0.022}
        color={color}
        anchorX="center"
        anchorY="bottom"
        renderOrder={1}
      >
        {poi.id}
      </Text>
    </group>
  );
}
