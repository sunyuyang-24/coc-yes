"use client";

import { useEffect, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

export function ApiStatus() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    fetch(`${API_BASE_URL}/api/health`)
      .then(r => { if (active) setOnline(r.ok); })
      .catch(() => { if (active) setOnline(false); });
    return () => { active = false; };
  }, []);

  if (online === null) return null;

  return (
    <span className="api-status-inline">
      <span className={`api-dot \${online ? "api-dot--online" : "api-dot--offline"}`} />
      {online ? "API 在线" : "API 离线"}
    </span>
  );
}
