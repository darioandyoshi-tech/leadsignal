"use client";

import { useRef, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Stars, Sphere } from "@react-three/drei";
import * as THREE from "three";

interface SignalGlobeProps {
  count?: number;
  accent?: string;
}

function OmahaMapDots({ count = 80, accent = "#f59e0b" }: SignalGlobeProps) {
  const meshRef = useRef<THREE.Points>(null);
  const pulseRef = useRef<THREE.Group>(null);

  const [positions, sizes] = useMemo(() => {
    const pos = new Float32Array(count * 3);
    const sz = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      // rough geographic disk around Omaha: lat ~41.25, lon ~-95.94
      const radius = 0.6 + Math.random() * 1.8;
      const angle = Math.random() * Math.PI * 2;
      const x = Math.cos(angle) * radius;
      const y = (Math.random() - 0.5) * 0.6;
      const z = Math.sin(angle) * radius;
      pos[i * 3] = x;
      pos[i * 3 + 1] = y;
      pos[i * 3 + 2] = z;
      sz[i] = Math.random() * 0.08 + 0.02;
    }
    return [pos, sz];
  }, [count]);

  useFrame(({ clock }) => {
    if (meshRef.current) {
      meshRef.current.rotation.y = clock.getElapsedTime() * 0.05;
    }
    if (pulseRef.current) {
      const t = clock.getElapsedTime();
      pulseRef.current.children.forEach((child, i) => {
        const mesh = child as THREE.Mesh;
        const s = 1 + Math.sin(t * 2 + i) * 0.3;
        mesh.scale.setScalar(s);
        const mat = mesh.material as THREE.MeshBasicMaterial;
        if (mat) mat.opacity = 0.6 - (s - 1) * 0.5;
      });
    }
  });

  return (
    <group>
      <points ref={meshRef}>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={count}
            array={positions}
            itemSize={3}
          />
          <bufferAttribute
            attach="attributes-size"
            count={count}
            array={sizes}
            itemSize={1}
          />
        </bufferGeometry>
        <pointsMaterial
          size={0.08}
          color={accent}
          transparent
          opacity={0.9}
          sizeAttenuation
        />
      </points>
      <group ref={pulseRef}>
        {[...Array(5)].map((_, i) => (
          <Sphere key={i} args={[0.08 + i * 0.04, 16, 16]} position={[0, 0, 0]}>
            <meshBasicMaterial color={accent} transparent opacity={0.2} wireframe />
          </Sphere>
        ))}
      </group>
    </group>
  );
}

function FloatingParticles({ count = 60 }: { count?: number }) {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const p = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i++) {
      p[i] = (Math.random() - 0.5) * 8;
    }
    return p;
  }, [count]);

  useFrame(({ clock }) => {
    if (ref.current) {
      ref.current.rotation.y = clock.getElapsedTime() * 0.02;
      ref.current.rotation.x = Math.sin(clock.getElapsedTime() * 0.1) * 0.05;
    }
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={count}
          array={positions}
          itemSize={3}
        />
      </bufferGeometry>
      <pointsMaterial size={0.03} color="#94a3b8" transparent opacity={0.35} sizeAttenuation />
    </points>
  );
}

export function SignalGlobe({ count = 80 }: SignalGlobeProps) {
  return (
    <div className="h-[420px] w-full rounded-2xl overflow-hidden border border-noir-700/50 bg-noir-900/30">
      <Canvas camera={{ position: [0, 1.5, 4.5], fov: 45 }} dpr={[1, 2]}>
        <color attach="background" args={["#020617"]} />
        <ambientLight intensity={0.4} />
        <pointLight position={[5, 5, 5]} intensity={1.2} color="#f59e0b" />
        <pointLight position={[-5, -2, -5]} intensity={0.8} color="#3b82f6" />
        <Stars radius={8} depth={40} count={400} factor={4} saturation={0.6} fade speed={1} />
        <FloatingParticles count={80} />
        <OmahaMapDots count={count} accent="#f59e0b" />
        <OrbitControls
          autoRotate
          autoRotateSpeed={0.8}
          enableZoom={false}
          enablePan={false}
          minPolarAngle={Math.PI / 3}
          maxPolarAngle={Math.PI / 1.7}
        />
      </Canvas>
    </div>
  );
}
