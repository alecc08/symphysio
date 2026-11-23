# Credits

## The Rod of Asclepius in the brand mark

The snake-and-staff inside the heart is not drawn from scratch. It is the
**U+2695 glyph geometry from [Twemoji](https://github.com/twitter/twemoji)**
(the three white shapes of `assets/svg/2695.svg`, on its 36×36 grid), scaled and
placed onto the heart.

- **Twemoji artwork** — © Twitter, Inc. and other contributors,
  [CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- The rest of the mark (heart, plaster, crutch, palette and composition) is
  original to Symphysio and is covered by the repository's MIT licence. The
  Twemoji-derived shapes are a derivative work, so the credit above travels with
  any redistribution of the mark.
- The geometry in this repository is the extracted shape data, generated into
  `frontend/src/components/icons/brandmark.ts` and the files in
  `frontend/public/icons/` by `scripts/gen_brand_assets.py`, which fetches the
  source glyph from the URL above.

Why the rod and not the caduceus: the single serpent on a staff is the medical
symbol the WHO, the AMA and the BMA use. The winged two-snake caduceus is
Hermes' staff and has been the emblem of commerce since antiquity; it is common
on US signage but it is the wrong symbol for care.

## Fonts, icons and libraries

No icon fonts and no emoji are used anywhere in the UI - every glyph in the app
is an inline SVG drawn for this project (`frontend/src/components/icons/`), with
the single exception of the rod noted above. Runtime and build dependencies are
pinned in `backend/uv.lock` and `frontend/package-lock.json`; each is an
independent MIT- or ISC-licensed package, and none of their artwork ships.
