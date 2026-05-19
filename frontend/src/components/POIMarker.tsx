import { Text } from '@react-three/drei';
import type { POI } from '../hooks/useFixtures';

interface Props {
  poi: POI;
}

export function POIMarker({ poi }: Props) {
  const { x, y: sceneZ, z: sceneY } = poi.location;

  return (
    <group position={[x, sceneY, sceneZ]}>
      <mesh>
        <boxGeometry args={[0.025, 0.025, 0.025]} />
        <meshStandardMaterial color="#ffdd44" emissive="#ffdd44" emissiveIntensity={0.6} />
      </mesh>
      <Text
        position={[0, 0.04, 0]}
        fontSize={0.022}
        color="#ffdd44"
        anchorX="center"
        anchorY="bottom"
        renderOrder={1}
      >
        {poi.id}
      </Text>
    </group>
  );
}
