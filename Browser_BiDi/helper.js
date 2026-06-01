// Copyright 2026 MarketSquare
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Bundled jsextension helper, loaded by the plugin via
// `initialize_js_extension`. It runs inside the Node process with direct
// access to the live Playwright `page`, and reads the correlation metadata
// (CDP target id + URL) the Python side needs to map a Playwright page to a
// BiDi browsing context (design.md D6). It is NOT exposed as a Robot keyword.

async function getCorrelationInfo(page, logger) {
    const info = { url: page.url(), targetId: null };
    try {
        // Chromium only: a tiny CDP call yields the target id, which aligns
        // with the BiDi context id under the mapper.
        const session = await page.context().newCDPSession(page);
        const { targetInfo } = await session.send("Target.getTargetInfo");
        info.targetId = targetInfo.targetId;
        await session.detach();
    } catch (err) {
        // Non-Chromium (e.g. Firefox) has no CDP; fall back to URL-only
        // matching on the Python side.
        logger("BiDi correlation: CDP target id unavailable (" + err.message + ")");
    }
    return info;
}
getCorrelationInfo.rfdoc = "Internal: returns {url, targetId} for BiDi correlation.";

exports.__esModule = true;
exports.getCorrelationInfo = getCorrelationInfo;
