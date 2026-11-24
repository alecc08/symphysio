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
import { useI18n } from "../i18n";

interface SessionValue {
  user: User | null;
  ready: boolean;
  busy: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, profile?: string) => Promise<void>;
  /** Language and time zone of the signed-in account, straight from the server. */
  preferences: () => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const { adopt, locale } = useI18n();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);

  const adoptUser = useCallback(
    (who: User) => {
      setUser(who);
      // The account outranks this device: it is the copy the server also writes
      // into emails and error responses, so the screen has to agree with them.
      adopt(who.locale);
    },
    [adopt],
  );

  const reload = useCallback(async () => {
    try {
      const { user: whoami } = await api.me();
      adoptUser(whoami);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setUser(null);
    }
  }, [adoptUser]);

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
          adoptUser(who);
        } finally {
          setBusy(false);
        }
      },
      register: async (email, password, profile) => {
        setBusy(true);
        try {
          // `profile` is sent explicitly whenever the caller offers one: the API
          // default is the postnatal set for old clients, while the sign-up card
          // starts on "Start empty". The two only agree because the SPA is explicit.
          // The language is sent at sign-up because it decides the language the
          // account is *seeded in*: preset names become rows, and rows are never
          // re-translated behind someone's back.
          const { user: who } = await api.register(email, password, profile, locale);
          adoptUser(who);
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
      preferences: async () => {
        const { user: who } = await api.me();
        adoptUser(who);
      },
    }),
    [user, ready, busy, reload, adoptUser, locale],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
