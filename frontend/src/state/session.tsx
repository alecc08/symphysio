/* Cookie-session state. The SPA never sees a token: it asks the API who it is. */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError, api } from "../api/client";
import type { User } from "../api/types";

interface SessionValue {
  user: User | null;
  ready: boolean;
  busy: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    try {
      const { user: whoami } = await api.me();
      setUser(whoami);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setUser(null);
    }
  }, []);

  useEffect(() => {
    void reload().finally(() => setReady(true));
  }, [reload]);

  const value = useMemo<SessionValue>(
    () => ({
      user,
      ready,
      busy,
      login: async (email, password) => {
        setBusy(true);
        try {
          const { user: who } = await api.login(email, password);
          setUser(who);
        } finally {
          setBusy(false);
        }
      },
      register: async (email, password) => {
        setBusy(true);
        try {
          const { user: who } = await api.register(email, password);
          setUser(who);
        } finally {
          setBusy(false);
        }
      },
      logout: async () => {
        setBusy(true);
        try {
          await api.logout();
        } finally {
          setUser(null);
          setBusy(false);
        }
      },
      reload,
    }),
    [user, ready, busy, reload],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
