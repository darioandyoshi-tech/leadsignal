"use client";

import { useRef, useMemo, useState, useCallback } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Stars, Html } from "@react-three/drei";
import * as THREE from "three";

interface GeoSignal {
  id: string;
  lat?: number;
  lng?: number;
  headline: string;
  signal_type: string;
  severity: number;
}

interface SignalGlobe3DMapProps {
  signals: GeoSignal[];
  accent?: string;
}

const EARTH_RADIUS = 2;

function latLngToVector3(lat: number, lng: number, radius: number) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lng + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta)
  );
}

function Earth({ signals, accent = "#f59e0b" }: SignalGlobe3DMapProps) {
  const groupRef = useRef<THREE.Group>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  const pins = useMemo(() => {
    return signals
      .filter((s): s is GeoSignal & { lat: number; lng: number } => typeof s.lat === "number" && typeof s.lng === "number" && !isNaN(s.lat) && !isNaN(s.lng))
      .map((s) => ({
        ...s,
        position: latLngToVector3(s.lat, s.lng, EARTH_RADIUS),
      }));
  }, [signals]);

  useFrame(({ clock }) => {
    if (groupRef.current) {
      groupRef.current.rotation.y = clock.getElapsedTime() * 0.05;
    }
  });

  return (
    <group ref={groupRef}>
      {/* Wireframe earth */}
      <mesh>
        <sphereGeometry args={[EARTH_RADIUS, 48, 48]} />
        <meshStandardMaterial
          color="#0f172a"
          emissive="#1e293b"
          emissiveIntensity={0.25}
          wireframe
          transparent
          opacity={0.55}
        />
      </mesh>

      {/* Inner glow core */}
      <mesh>
        <sphereGeometry args={[EARTH_RADIUS * 0.97, 32, 32]} />
        <meshBasicMaterial color="#020617" transparent opacity={0.9} />
      </mesh>

      {/* Latitude / longitude helper rings */}
      {[...Array(6)].map((_, i) => (
        <mesh key={i} rotation={[Math.PI / 2, 0, 0]} position={[0, ((i - 2.5) / 2.5) * EARTH_RADIUS, 0]}>
          <ringGeometry args={[EARTH_RADIUS * 0.2, EARTH_RADIUS * 1.01, 64]} />
          <meshBasicMaterial color="#334155" transparent opacity={0.12} side={THREE.DoubleSide} />
        </mesh>
      ))}

      {/* Pins */}
      {pins.map((s) => (
        <SignalPin
          key={s.id}
          signal={s}
          position={s.position}
          color={accent}
          hovered={hovered === s.id}
          onHover={setHovered}
        />
      ))}
    </group>
  );
}

function SignalPin({
  signal,
  position,
  color,
  hovered,
  onHover,
}: {
  signal: GeoSignal;
  position: THREE.Vector3;
  color: string;
  hovered: boolean;
  onHover: (id: string | null) => void;
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      const baseScale = hovered ? 1.6 : 1;
      const pulse = 1 + Math.sin(clock.getElapsedTime() * 3 + parseInt(signal.id, 36) % 10) * 0.15;
      meshRef.current.scale.setScalar(baseScale * pulse);
    }
  });

  return (
    <group position={position}>
      <mesh
        ref={meshRef}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHover(signal.id);
        }}
        onPointerOut={() => onHover(null)}
      >
        <sphereGeometry args={[0.045, 16, 16]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={hovered ? 1.2 : 0.6}
          roughness={0.3}
          metalness={0.6}
        />
      </mesh>
      {/* Beam to surface core */}
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, 0, -0.06]}>
        <cylinderGeometry args={[0.008, 0.001, 0.12, 8]} />
        <meshBasicMaterial color={color} transparent opacity={0.5} />
      </mesh>

      {hovered && (
        <Html distanceFactor={10}>
          <div className="pointer-events-none w-56 rounded-lg border border-noir-700/80 bg-noir-900/95 p-3 text-xs shadow-xl backdrop-blur-md">
            <div className="mb-1 font-semibold text-noir-100">{signal.headline}</div>
            <div className="text-noir-400">{signal.signal_type}</div>
            <div className="mt-1 text-noir-500">Severity {signal.severity}</div>
            <div className="mt-1 text-noir-500">
              {signal.lat?.toFixed(4)}, {signal.lng?.toFixed(4)}
            </div>
          </div>
        </Html>
      )}
    </group>
  );
}

function Scene({ signals }: { signals: GeoSignal[] }) {
  const { camera } = useThree();

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 10, 10]} intensity={1.5} color="#f59e0b" />
      <pointLight position={[-10, -5, -10]} intensity={0.8} color="#3b82f6" />
      <Stars radius={20} depth={50} count={1000} factor={4} saturation={0.5} fade speed={1} />
      <Earth signals={signals} accent="#f59e0b" />
      <OrbitControls
        autoRotate
        autoRotateSpeed={0.5}
        enableZoom={true}
        enablePan={false}
        minDistance={3.5}
        maxDistance={12}
      />
    </>
  );
}

export function SignalGlobe3DMap({ signals }: { signals: GeoSignal[] }) {
  const filtered = useMemo(() => {
    // Dedupe by lat/lng rounded to 3 decimals and cap at 120 pins for performance.
    const seen = new Set<string>();
    return signals
      .filter((s): s is GeoSignal & { lat: number; lng: number } => typeof s.lat === "number" && typeof s.lng === "number" && !isNaN(s.lat) && !isNaN(s.lng))
      .filter((s) => {
        const key = `${s.lat.toFixed(3)},${s.lng.toFixed(3)}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 120);
  }, [signals]);

  return (
    <div className="h-[540px] w-full overflow-hidden rounded-2xl border border-noir-700/50 bg-noir-950">
      <Canvas camera={{ position: [0, 0, 6], fov: 45 }} dpr={[1, 2]}>
        <color attach="background" args={["#020617"]} />
        <Scene signals={filtered} />
      </Canvas>
    </div>
  );
}
