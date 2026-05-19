import { useCallback, useEffect, useState } from "react";
import { me, refreshSession } from "../api/client.js";

export function useSession() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await me();
      setUser(data);
      setError(null);
    } catch (err) {
      if (err.status === 401) {
        try {
          await refreshSession();
          const data = await me();
          setUser(data);
          setError(null);
          return;
        } catch {
          setUser(null);
        }
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return { user, loading, error, reload: load };
}
