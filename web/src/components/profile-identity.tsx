"use client";

import { useAuth } from "@/lib/auth";

export default function ProfileIdentity() {
  const { user } = useAuth();

  return (
    <h1 className="mt-1 text-3xl font-black tracking-[-0.05em] text-white">
      {user?.full_name ?? user?.username}
    </h1>
  );
}
