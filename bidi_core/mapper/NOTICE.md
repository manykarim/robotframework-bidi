# Vendored: chromium-bidi mapper

`mapperTab.js` is the compiled IIFE bundle of
[chromium-bidi](https://github.com/GoogleChromeLabs/chromium-bidi)
(`chromium-bidi@16.0.1`, file `lib/iife/mapperTab.js`), © Google LLC,
licensed under **Apache License 2.0** (compatible with this project).

It is loaded into a hidden Chrome tab over CDP to provide WebDriver BiDi without
chromedriver (see `Browser_BiDi/mapper_client.py`). This is the same mapper
chromedriver bundles; we run it client-side instead.

**Updating:** download a version aligned with your target Chrome from
`https://unpkg.com/chromium-bidi@<version>/lib/iife/mapperTab.js` and replace
this file. Validated with Chrome 147 + chromium-bidi 16.0.1.
