// The offline shell's words, in the language the person chose.
//
// Why this is a separate file with its own strings instead of the app's
// dictionary: the shell is what the service worker serves when the app bundle
// cannot load, so it must not depend on that bundle. Why not a second HTML file
// per language: the service worker cannot see the choice — the person's language
// lives in localStorage, which is not available in a worker — while this page runs
// in the page, where it is. The copy is five short strings; drift between here and
// src/i18n is cheap to fix and obvious on screen.
//
// Order of authority matches the app: stored choice first, then the browser.
(function () {
  "use strict";

  var COPY = {
    en: {
      title: "Offline — Symphysio",
      heading: "You are offline",
      body:
        "Symphysio needs the server to log anything — a log you cannot confirm is a log you cannot " +
        "trust. Reconnect and tap again.",
      action: "Try again",
    },
    fr: {
      title: "Hors ligne — Symphysio",
      heading: "Vous êtes hors ligne",
      body:
        "Symphysio a besoin du serveur pour consigner quoi que ce soit — une entrée que vous ne " +
        "pouvez pas confirmer est une entrée dont on ne peut pas se fier. Reconnectez-vous, puis " +
        "réessayez.",
      action: "Réessayer",
    },
  };

  var stored = null;
  try {
    stored = window.localStorage.getItem("symphysio.locale");
  } catch (error) {
    stored = null; // private mode: fall back to the browser
  }

  var locale = stored === "en" || stored === "fr" ? stored : null;
  if (!locale) {
    var tags = navigator.languages || [navigator.language];
    for (var i = 0; i < tags.length; i += 1) {
      if (typeof tags[i] === "string" && tags[i].toLowerCase().indexOf("fr") === 0) {
        locale = "fr";
        break;
      }
    }
  }
  if (!locale) return; // the page is already English

  var copy = COPY[locale];
  document.documentElement.lang = locale === "fr" ? "fr-CA" : "en-CA";
  document.title = copy.title;
  var heading = document.querySelector("h1");
  var body = document.querySelector("main p");
  var action = document.querySelector("a.button");
  if (heading) heading.textContent = copy.heading;
  if (body) body.textContent = copy.body;
  if (action) action.textContent = copy.action;
})();
