/* One language for the whole app, chosen in two places and remembered in three.

   The order of authority, which matters more than it looks:

   1. The signed-in account's `locale`. The server keeps it because it also
      decides what *language the emails are written in* and what language a
      failed request answers in — neither of which a browser setting can reach.
   2. `localStorage` on this device, which is what makes the sign-in screen and
      the sign-up picker speak French before there is an account to ask.
   3. `navigator.language`, so a phone set to French-Canada gets French without
      anyone choosing.

   Changing the language while signed in also PATCHes the account, so the choice
   walks to the next device. Changing it while signed out changes only this
   device — there is nothing to write to.

   Nothing here re-renders the *content* of stored rows: a symptom called
   "Urine Leak" stays called that in a French app, because it is the person's
   data, not the app's chrome. See docs/API.md.
*/

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { api } from "../api/client";
import { en, type MessageKey } from "./en";
import { fr } from "./fr";
import {
  localeTag,
  normalizeLocale,
  preferredLocale,
  STORAGE_KEY,
  type Locale,
} from "./resolve";

export type { Locale };
export { localeTag, normalizeLocale, preferredLocale };
export const SUPPORTED: readonly Locale[] = ["en", "fr"];

const TABLES: Record<Locale, Record<MessageKey, string>> = { en, fr };

interface Interpolation {
  [placeholder: string]: string | number;
}

export interface I18nValue {
  locale: Locale;
  /** BCP 47 tag for Intl: `fr-CA` / `en-CA`. */
  tag: string;
  /**
   * Look up a string. Passing `count` also picks the plural form: `key` is the
   * plural ("2 sessions") and `key_one` the singular, so a sentence is written
   * once per language instead of twice.
   */
  t: (key: MessageKey, params?: Interpolation) => string;
  /** Choose a language. While signed in the account is written to as well. */
  choose: (next: Locale) => void;
  /** Adopt the language of the account that just signed in. */
  adopt: (locale: unknown) => void;
}

const I18nContext = createContext<I18nValue | null>(null);

function applyDocumentLocale(locale: Locale) {
  document.documentElement.lang = localeTag(locale);
  document.documentElement.dataset.locale = locale;
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>(() => preferredLocale());

  useEffect(() => {
    applyDocumentLocale(locale);
    try {
      globalThis.localStorage?.setItem(STORAGE_KEY, locale);
    } catch {
      /* not fatal: the language is still right for this session */
    }
    // The server writes its own words — a failed login, a validation error, the
    // sign-up confirmation mail — and this is how it knows which language. The
    // API client reads it from here rather than from a second copy of the choice.
    api.setLocale(locale);
  }, [locale]);

  const t = useCallback(
    (key: MessageKey, params?: Interpolation) => {
      const table = TABLES[locale];
      // Plural form: passing `count` picks `<key>_one` when it is 1, so a
      // sentence is written once per language instead of as a One/Many pair.
      // Callers that already branch themselves keep working — the `_one` keys
      // are ordinary keys.
      let chosen = key;
      if (params && Number(params.count) === 1) {
        const singular = `${key}_one` as MessageKey;
        if (table[singular]) chosen = singular;
      }
      // A missing key is a bug in the dictionary, and the type makes that
      // impossible at build time. Falling back to English keeps the screen
      // readable rather than showing `auth.sign in` to a patient.
      const raw = table[chosen] ?? en[chosen] ?? chosen;
      if (!params) return raw;
      return raw.replace(/\{(\w+)\}/g, (whole, name: string) =>
        name in params ? String(params[name]) : whole,
      );
    },
    [locale],
  );

  const choose = useCallback((next: Locale) => {
    const settled = normalizeLocale(next);
    setLocale(settled);
    // Signed in? The account is the authority, so write it there too. Failure is
    // silent on purpose: the device is already in the new language, and an
    // offline device must not refuse to change its own wording.
    void api.patchPreferences({ locale: settled }).catch(() => undefined);
  }, []);

  const adopt = useCallback((raw: unknown) => {
    if (typeof raw !== "string" || !raw) return;
    const wanted = normalizeLocale(raw);
    setLocale((current) => (current === wanted ? current : wanted));
  }, []);

  const value = useMemo<I18nValue>(
    () => ({ locale, tag: localeTag(locale), t, choose, adopt }),
    [locale, t, choose, adopt],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useI18n must be used inside I18nProvider");
  return value;
}
