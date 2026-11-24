"""The server's words, in both languages.

Split out of ``app/i18n.py`` because it is a table, not logic, and the table is
the part a reviewer should be able to read as two columns. ``tests/test_i18n.py``
walks it and fails on a blank cell, so a key cannot ship half-translated.

Key groups: ``err.*`` (API responses), ``pw.*`` (password policy), ``mail.*``
(confirmation and reset emails), ``csv.*`` (the export header row).
"""

from __future__ import annotations

# The two codes, defined here so the table has no import back into `i18n` (which
# imports this module). `i18n` re-exports them as its own public names.
EN = "en"
FR = "fr"

MESSAGES: dict[str, dict[str, str]] = {
    # -- auth and session ------------------------------------------------
    "err.not_authenticated": {
        EN: "Not authenticated",
        FR: "Non authentifié",
    },
    "err.csrf": {
        EN: "CSRF token missing or invalid.",
        FR: "Jeton CSRF manquant ou invalide.",
    },
    "err.body_too_large": {
        EN: "Request body too large",
        FR: "Corps de la requête trop volumineux",
    },
    "err.too_many_attempts": {
        EN: "Too many attempts. Try again later.",
        FR: "Trop de tentatives. Réessayez plus tard.",
    },
    "err.registration_closed": {
        EN: "Registration is closed on this instance.",
        FR: "L'inscription est fermée sur cette instance.",
    },
    "err.email_taken": {
        EN: "An account with that email already exists.",
        FR: "Un compte avec cette adresse courriel existe déjà.",
    },
    "err.bad_credentials": {
        EN: "Email or password is incorrect.",
        FR: "Adresse courriel ou mot de passe incorrect.",
    },
    "err.confirm_first": {
        EN: "Confirm your email first — we have just sent you a new link.",
        FR: "Confirmez d'abord votre courriel — nous venons de vous envoyer un nouveau lien.",
    },
    "err.verify_expired": {
        EN: "That confirmation link has expired. Request a new one.",
        FR: "Ce lien de confirmation a expiré. Demandez-en un nouveau.",
    },
    "err.verify_used": {
        EN: "That confirmation link has already been used.",
        FR: "Ce lien de confirmation a déjà été utilisé.",
    },
    "err.verify_invalid": {
        EN: "That confirmation link is not valid.",
        FR: "Ce lien de confirmation n'est pas valide.",
    },
    "err.verify_disabled": {
        EN: "Email confirmation is not enabled on this server.",
        FR: "La confirmation par courriel n'est pas activée sur ce serveur.",
    },
    "err.already_verified": {
        EN: "This account is already confirmed.",
        FR: "Ce compte est déjà confirmé.",
    },
    "err.send_cap": {
        EN: "Only {limit} emails per hour are sent.",
        FR: "Seulement {limit} courriels par heure sont envoyés.",
    },
    "err.no_mail_transport": {
        EN: "Password recovery needs email configured on this server.",
        FR: "La récupération du mot de passe exige un envoi de courriel configuré sur ce serveur.",
    },
    "err.reset_expired": {
        EN: "That reset link has expired. Request a new one.",
        FR: "Ce lien de réinitialisation a expiré. Demandez-en un nouveau.",
    },
    "err.reset_used": {
        EN: "That reset link has already been used.",
        FR: "Ce lien de réinitialisation a déjà été utilisé.",
    },
    "err.reset_invalid": {
        EN: "That reset link is not valid.",
        FR: "Ce lien de réinitialisation n'est pas valide.",
    },
    "err.reset_failed": {
        EN: "Could not complete the reset. Try a new link.",
        FR: "Impossible de terminer la réinitialisation. Essayez un nouveau lien.",
    },
    # -- catalog, logs, plan, analytics ----------------------------------
    "err.bad_catalog_kind": {
        EN: "Unknown catalog kind",
        FR: "Type de catalogue inconnu",
    },
    "err.duplicate_name": {
        EN: "You already have a catalog item with that name.",
        FR: "Vous avez déjà un élément de catalogue avec ce nom.",
    },
    "err.catalog_not_found": {
        EN: "Catalog item not found",
        FR: "Élément de catalogue introuvable",
    },
    "err.log_not_found": {
        EN: "Log entry not found",
        FR: "Entrée du journal introuvable",
    },
    "err.bad_update": {
        EN: "Invalid update payload",
        FR: "Charge utile de mise à jour invalide",
    },
    "err.nothing_to_change": {
        EN: "Nothing to change",
        FR: "Rien à modifier",
    },
    "err.plan_not_found": {
        EN: "Plan event not found",
        FR: "Événement du plan introuvable",
    },
    "err.bad_window": {
        EN: "Unknown window; try one of {windows}",
        FR: "Fenêtre inconnue; essayez l'une de celles-ci : {windows}",
    },
    "err.unknown_symptom": {
        EN: "Unknown symptom definition",
        FR: "Définition de symptôme inconnue",
    },
    "err.unknown_definition": {
        EN: "Unknown {kind} definition: {definition_id}",
        FR: "Définition {kind} inconnue : {definition_id}",
    },
    "err.archived_definition": {
        EN: "That {kind} is archived; unarchive it first.",
        FR: "Ce {kind} est archivé ; désarchivez-le d'abord.",
    },
    "err.bad_timezone": {
        EN: "Unknown time zone",
        FR: "Fuseau horaire inconnu",
    },
    # The three event kinds, spelled the way they read inside a sentence. The
    # API's own vocabulary stays `exercise` / `symptom` / `context` everywhere.
    "kind.exercise": {EN: "exercise", FR: "exercice"},
    "kind.symptom": {EN: "symptom", FR: "symptôme"},
    "kind.context": {EN: "context", FR: "contexte"},
    # -- password policy --------------------------------------------------
    "pw.too_short": {
        EN: "Password must be at least {limit} characters.",
        FR: "Le mot de passe doit comporter au moins {limit} caractères.",
    },
    "pw.too_long": {
        EN: "Password must be at most {limit} characters.",
        FR: "Le mot de passe doit comporter au plus {limit} caractères.",
    },
    "pw.whitespace": {
        EN: "Password must not start or end with whitespace.",
        FR: "Le mot de passe ne doit pas commencer ni finir par un espace.",
    },
    "pw.common": {
        EN: "That is one of the most common passwords. Pick another.",
        FR: "C'est l'un des mots de passe les plus courants. Choisissez-en un autre.",
    },
    "pw.in_email": {
        EN: "Password must not contain your email address.",
        FR: "Le mot de passe ne doit pas contenir votre adresse courriel.",
    },
    "pw.in_domain": {
        EN: "Password must not contain your email domain.",
        FR: "Le mot de passe ne doit pas contenir le domaine de votre courriel.",
    },
    "pw.repetitive": {
        EN: "Password is too repetitive or keyboard-sequential.",
        FR: "Le mot de passe est trop répétitif ou suit une suite du clavier.",
    },
    "pw.few_distinct": {
        EN: "Password uses too few distinct characters.",
        FR: "Le mot de passe utilise trop peu de caractères différents.",
    },
    # -- emails ----------------------------------------------------------
    # Short pieces, not one blob per language: the plain-text mail and its HTML
    # twin quote the same lines, so a translation cannot drift between them.
    "mail.verify_subject": {
        EN: "Confirm your Symphysio account",
        FR: "Confirmez votre compte Symphysio",
    },
    "mail.verify_heading": {
        EN: "Confirm your email",
        FR: "Confirmez votre courriel",
    },
    "mail.verify_open": {
        EN: "Open this link to confirm the address you signed up with. It works for "
            "{count} {unit} and can only be used once.",
        FR: "Ouvrez ce lien pour confirmer l'adresse utilisée à l'inscription. Il est "
            "valide {count} {unit} et ne peut servir qu'une seule fois.",
    },
    "mail.verify_harmless": {
        EN: "You can keep using Symphysio while it is unconfirmed. Confirming only "
            "means you can recover the account if you lose your phone.",
        FR: "Vous pouvez continuer d'utiliser Symphysio même si l'adresse n'est pas "
            "confirmée. Confirmer ne sert qu'à une chose : récupérer le compte si "
            "vous perdez votre téléphone.",
    },
    "mail.verify_not_you": {
        EN: "If you did not create this account, ignore this email — nothing has been "
            "confirmed, and it will expire on its own.",
        FR: "Si vous n'avez pas créé ce compte, ignorez ce courriel — rien n'a été "
            "confirmé, et le lien expirera de lui-même.",
    },
    "mail.verify_button": {
        EN: "Confirm account",
        FR: "Confirmer le compte",
    },
    "mail.reset_subject": {
        EN: "Reset your Symphysio password",
        FR: "Réinitialisez votre mot de passe Symphysio",
    },
    "mail.reset_heading": {
        EN: "Reset your password",
        FR: "Réinitialiser votre mot de passe",
    },
    "mail.reset_open": {
        EN: "Open this link and choose a new password. It works for {count} {unit} "
            "and can only be used once.",
        FR: "Ouvrez ce lien et choisissez un nouveau mot de passe. Il est valide "
            "{count} {unit} et ne peut servir qu'une seule fois.",
    },
    "mail.reset_signout": {
        EN: "Setting a new password signs every other device out of this account.",
        FR: "Définir un nouveau mot de passe déconnecte tous les autres appareils de ce compte.",
    },
    "mail.reset_not_you": {
        EN: "If you did not ask for this, nothing needs doing: the link expires and "
            "no password changes until someone uses it.",
        FR: "Si vous n'avez rien demandé, inutile d'agir : le lien expire et aucun mot "
            "de passe ne change tant que quelqu'un ne l'utilise pas.",
    },
    "mail.reset_button": {
        EN: "Choose a new password",
        FR: "Choisir un nouveau mot de passe",
    },
    "mail.never_health": {
        EN: "Symphysio never sends health information by email.",
        FR: "Symphysio n'envoie jamais de renseignement sur la santé par courriel.",
    },
    # Units are their own keys because the plural differs by language, not by rule
    # we get to apply: "1 hour" / "2 hours", "1 heure" / "2 heures".
    "mail.hour_one": {EN: "hour", FR: "heure"},
    "mail.hour_many": {EN: "hours", FR: "heures"},
    "mail.minute_one": {EN: "minute", FR: "minute"},
    "mail.minute_many": {EN: "minutes", FR: "minutes"},
    # -- the CSV header row ----------------------------------------------
    # Keyed by the column name itself (`csv.<column>`), so `export.py` builds the
    # header straight from CSV_COLUMNS and a new column without a translation is a
    # test failure rather than a silently English cell. Column *values* stay
    # machine-readable: only the header line is in the reader's language.
    "csv.event_type": {EN: "event_type", FR: "type_événement"},
    "csv.id": {EN: "id", FR: "id"},
    "csv.definition": {EN: "definition", FR: "nom"},
    "csv.definition_id": {EN: "definition_id", FR: "id_définition"},
    "csv.occurred_at_utc": {EN: "occurred_at_utc", FR: "survenu_le_utc"},
    "csv.occurred_utc": {EN: "occurred_utc", FR: "survenu_utc"},
    "csv.local_time": {EN: "local_time", FR: "heure_locale"},
    "csv.tz_offset_min": {EN: "tz_offset_min", FR: "décalage_tz_min"},
    "csv.logged_at_utc": {EN: "logged_at_utc", FR: "saisi_le_utc"},
    "csv.metric": {EN: "metric", FR: "valeur"},
    "csv.metric_name": {EN: "metric_name", FR: "nom_de_la_mesure"},
    "csv.sets_done": {EN: "sets_done", FR: "séries_faites"},
    "csv.reps_done": {EN: "reps_done", FR: "répétitions_faites"},
    "csv.duration_sec": {EN: "duration_sec", FR: "durée_sec"},
    "csv.duration_min": {EN: "duration_min", FR: "durée_min"},
    "csv.severity": {EN: "severity", FR: "gravité"},
    "csv.pain_during": {EN: "pain_during", FR: "douleur_pendant"},
    "csv.intensity": {EN: "intensity", FR: "intensité"},
    "csv.body_region": {EN: "body_region", FR: "région_du_corps"},
    "csv.category": {EN: "category", FR: "catégorie"},
    "csv.severity_default": {EN: "severity_default", FR: "gravité_par_défaut"},
    "csv.note": {EN: "note", FR: "note"},
}
