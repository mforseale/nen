"use client";

import { useEffect, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading, authError } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user && !authError) router.replace("/login");
  }, [authError, loading, router, user]);

  if (loading || (!user && !authError)) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-400" role="status">
        Проверяем вход…
      </div>
    );
  }

  if (authError) {
    return (
      <div className="mx-auto mt-16 max-w-md rounded-2xl border border-red-200/10 bg-black/60 p-6 text-center">
        <p className="text-sm text-red-200">{authError}</p>
        <p className="mt-2 text-xs text-slate-400">Запусти API и обнови страницу.</p>
      </div>
    );
  }

  return <>{children}</>;
}
