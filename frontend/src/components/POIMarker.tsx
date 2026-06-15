import { Billboard, Text } from '@react-three/drei';
import type { POI } from '../hooks/useFixtures';

interface Props {
  poi: POI;
  active: boolean;
  onSelect?: (poi: POI) => void;
}

export function POIMarker({ poi, active, onSelect }: Props) {
  const { x, y: sceneZ, z: sceneY } = poi.location;
  const isRef = poi.id.startsWith('ref_');
  const color = isRef ? '#4da6ff' : active ? '#7df2a7' : '#ffdd44';
  const size = isRef ? 0.025 : active ? 0.036 : 0.025;

  return (
    <group
      position={[x, sceneY, sceneZ]}
      onClick={(event) => {
        event.stopPropagation();
        onSelect?.(poi);
      }}
    >
      {isRef ? (
        <Billboard>
          <mesh>
            <circleGeometry args={[size / 2, 24]} />
            <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.75} />
          </mesh>
        </Billboard>
      ) : (
        <mesh>
          <boxGeometry args={[size, size, size]} />
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={active ? 1 : 0.6} />
        </mesh>
      )}
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
