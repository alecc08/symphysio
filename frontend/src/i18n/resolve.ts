/* Where the language choice lives, with no imports of its own.

   Split out because two places need to read it before anything renders: the React
   provider (which owns it) and the API client (which has to put it in the
   `Accept-Language` header of the very first request). The first request matters
   because the server's answer — the sign-up profile list, a validation error, the
   confirmation mail — is written in that language, so a client that asks in
   English and then switches gets one answer in the wrong language.

   No circular import is possible from here, which is the whole reason the file
   exists: `api/client.ts` cannot import the provider, and the provider imports
   the client.
*/

export type Locale = "en" | "fr";

export const STORAGE_KEY = "symphysio.locale";

/** `fr`, `fr-CA`, `FR_ca` → fr; everything else → en. Mirrors the server's rule
 *  (app/i18n.py) so the two never disagree about who gets French. */
export function normalizeLocale(raw: unknown): Locale {
  if (typeof raw !== "string") return "en";
  const tag = raw.trim().toLowerCase().split(/[-_;]/)[0];
  return tag === "fr" ? "fr" : "en";
}

export function localeTag(locale: Locale): string {
  // fr-CA and en-CA, not fr-FR / en-US. The region decides how a clock reads:
  // a Montreal browser writes "9 h 05", a French one "9:05", and Canadian
  // English writes "9:05 a.m." where American English writes "9:05 AM". Numbers
  // too — this tag is what makes a severity average print -1,2 in French.
  return locale === "fr" ? "fr-CA" : "en-CA";
}

/** What this device was last told to use, if anything. */
export function storedLocale(): Locale | null {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    return raw === "en" || raw === "fr" ? raw : null;
  } catch {
    return null; // private mode: the preference simply does not persist
  }
}

/** The browser's own order is the answer: a phone that lists `fr-CA` first is a
 *  French phone. A German phone listing `de, en` gets English, not French. */
export function browserLocale(): Locale {
  const nav = globalThis.navigator;
  const tags = nav?.languages ?? (nav?.language ? [nav.language] : []);
  for (const tag of tags) {
    if (typeof tag === "string" && normalizeLocale(tag) === "fr") return "fr";
  }
  return "en";
}

export function preferredLocale(): Locale {
  return storedLocale() ?? browserLocale();
}
