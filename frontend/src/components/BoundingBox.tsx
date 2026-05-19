export function BoundingBox() {
  return (
    <mesh position={[0.5, 0.5, 0.5]}>
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial color="#2a3a4a" wireframe />
    </mesh>
  );
}
