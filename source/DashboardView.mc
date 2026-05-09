using Toybox.Graphics;
using Toybox.System;
using Toybox.Timer;
using Toybox.WatchUi;

class DashboardView extends WatchUi.View {
    var model;
    var timer;
    var frame;
    var largePetFrames;
    var loadedPetState;
    var tick;
    var frameStartedMs;
    var sprites;

    function initialize(modelRef) {
        View.initialize();
        model = modelRef;
        frame = 0;
        tick = 0;
        timer = null;
        largePetFrames = [];
        loadedPetState = "";
        frameStartedMs = 0;
        sprites = new CodexPetSprites();
    }

    function onLayout(dc) {
        ensureTimer();
    }

    function onShow() {
        ensureTimer();
        syncPetFrames();
        model.refresh();
    }

    function ensureTimer() {
        if (timer != null) {
            return;
        }
        timer = new Timer.Timer();
        timer.start(method(:onTick), 250, true);
    }

    function onHide() {
        if (timer != null) {
            timer.stop();
            timer = null;
        }
    }

    function onTick() as Void {
        tick++;
        if (model.autoRefresh && tick % 80 == 0) {
            model.refresh();
        }
        if (model.isPetScreen()) {
            syncPetFrames();
            WatchUi.requestUpdate();
        }
    }

    function syncPetFrames() {
        var state = model.petAnimationState();
        if (largePetFrames.size() > 0 && codexTextEquals(loadedPetState, state)) {
            return;
        }

        loadPetFrames(state);
    }

    function loadPetFrames(state) {
        loadedPetState = state;
        frameStartedMs = System.getTimer();
        if (codexTextEquals(state, "jumping")) {
            frame = 3;
        } else {
            frame = 0;
        }

        largePetFrames = sprites.framesFor(state);
    }

    function onUpdate(dc) {
        ensureTimer();
        if (model.isPetScreen()) {
            syncPetFrames();
            updateAnimationFrame();
        }

        var w = dc.getWidth();
        var h = dc.getHeight();
        var palette = new CodexTheme(dc);
        palette.clear();

        if (model.isTaskDetails()) {
            drawTaskDetails(dc, palette, w, h);
        } else if (model.isTaskOverview()) {
            drawTaskOverview(dc, palette, w, h);
        } else {
            drawPetHome(dc, palette, w, h);
        }
    }

    function updateAnimationFrame() {
        if (largePetFrames.size() == 0) {
            frame = 0;
            return;
        }
        if (frameStartedMs == 0) {
            frameStartedMs = System.getTimer();
        }

        var interval = sprites.frameInterval(loadedPetState);

        var elapsed = System.getTimer() - frameStartedMs;
        if (elapsed < 0) {
            elapsed = 0;
            frameStartedMs = System.getTimer();
        }
        frame = (elapsed / interval) % largePetFrames.size();
        if (frame < 0 || frame >= largePetFrames.size()) {
            frame = 0;
        }
    }

    function drawTopTime(dc, palette, w) {
        dc.setColor(palette.ink, Graphics.COLOR_TRANSPARENT);
        dc.drawText(w / 2, 10, Graphics.FONT_TINY, fit(model.updatedAt, 12), Graphics.TEXT_JUSTIFY_CENTER);

        var statusColor = model.hasNetworkError ? palette.warn : palette.good;
        dc.setColor(statusColor, statusColor);
        dc.fillCircle(w - 46, 18, 4);
    }

    function drawPetHome(dc, palette, w, h) {
        drawTopTime(dc, palette, w);

        var bitmap = largePetFrames[frame];
        var centerX = w / 2;
        var petTop = homePetTop(h);

        dc.drawBitmap(centerX - bitmap.getWidth() / 2, petTop, bitmap);

        dc.setColor(palette.accent, Graphics.COLOR_TRANSPARENT);
        dc.drawText(centerX - 108, homeCounterY(h), Graphics.FONT_SMALL, "(" + model.runningTaskCount().toString() + ")", Graphics.TEXT_JUSTIFY_CENTER);

        dc.setColor(model.hasNetworkError ? palette.warn : palette.subtle, Graphics.COLOR_TRANSPARENT);
        drawHomeMessage(dc, palette, centerX, homeMessageY(h), w - 82);

        drawPageDots(dc, palette, w, h, 0);
    }

    function homePetTop(h) {
        if (h < 340) {
            return 38;
        }
        return 45;
    }

    function homeCounterY(h) {
        return homePetTop(h) + 120;
    }

    function homeMessageY(h) {
        if (h < 340) {
            return h - 72;
        }
        return h - 130;
    }

    function drawHomeMessage(dc, palette, centerX, y, width) {
        var text = latestMessageText();
        var maxChars = width / 11;
        if (maxChars > 26) {
            maxChars = 26;
        }
        if (maxChars < 14) {
            maxChars = 14;
        }

        dc.setColor(model.hasNetworkError ? palette.warn : palette.subtle, Graphics.COLOR_TRANSPARENT);
        if (text.length() <= maxChars) {
            dc.drawText(centerX, y, Graphics.FONT_XTINY, text, Graphics.TEXT_JUSTIFY_CENTER);
            return;
        }

        var line1 = text.substring(0, maxChars);
        var rest = text.substring(maxChars, text.length());
        if (rest.length() > maxChars - 1) {
            rest = rest.substring(0, maxChars - 1) + "...";
        }
        dc.drawText(centerX, y, Graphics.FONT_XTINY, line1, Graphics.TEXT_JUSTIFY_CENTER);
        dc.drawText(centerX, y + 27, Graphics.FONT_XTINY, rest, Graphics.TEXT_JUSTIFY_CENTER);
    }

    function latestMessageText() {
        if (model.hasNetworkError || !model.hasSeenTaskPayload) {
            return homeStatusText();
        }

        var message = model.topMessage();
        var body = model.safeString(message["body"]);
        if (body.length() > 0) {
            return body;
        }
        return homeStatusText();
    }

    function drawTaskOverview(dc, palette, w, h) {
        drawTopTime(dc, palette, w);

        var rendered = 0;
        var index = model.overviewTaskIndexForSlot(0);
        if (index >= 0) {
            var topW = contextTaskWidth(w, 0);
            drawContextTaskRow(dc, palette, model.taskAt(index), (w - topW) / 2, 44, topW, 52);
            rendered++;
        }

        index = model.overviewTaskIndexForSlot(1);
        if (index >= 0) {
            var featuredW = w - 46;
            drawFeaturedTask(dc, palette, model.taskAt(index), (w - featuredW) / 2, 104, featuredW, 98);
            rendered++;
        }

        index = model.overviewTaskIndexForSlot(2);
        if (index >= 0) {
            var bottomW = contextTaskWidth(w, 2);
            drawContextTaskRow(dc, palette, model.taskAt(index), (w - bottomW) / 2, 212, bottomW, 52);
            rendered++;
        }

        if (rendered == 0) {
            dc.setColor(palette.subtle, Graphics.COLOR_TRANSPARENT);
            dc.drawText(w / 2, 145, Graphics.FONT_TINY, "No task updates yet", Graphics.TEXT_JUSTIFY_CENTER);
        }

        if (model.hasNetworkError) {
            dc.setColor(palette.warn, Graphics.COLOR_TRANSPARENT);
            dc.drawText(w / 2, 254, Graphics.FONT_TINY, fit(model.status, 30), Graphics.TEXT_JUSTIFY_CENTER);
        }

        drawTaskPositionDots(dc, palette, w, h);
    }

    function drawFeaturedTask(dc, palette, message, x, y, width, height) {
        var tone = model.taskAccentKey(message);
        var accent = palette.accentFor(tone);
        var bg = palette.selection;
        if (codexTextEquals(tone, "success") || codexTextEquals(tone, "done")) {
            bg = 0x124222;
        }

        fillPill(dc, accent, x, y, width, height);
        fillPill(dc, bg, x + 3, y + 3, width - 6, height - 6);
        drawTaskIcon(dc, palette, x + 34, y + height / 2, tone, bg);

        var textX = x + 64;
        var textWidth = width - 86;
        drawWrappedText(dc, taskPreviewText(message), Graphics.FONT_XTINY, textX, y + 13, textWidth, 22, 3, palette.ink);
    }

    function drawContextTaskRow(dc, palette, message, x, y, width, height) {
        var tone = model.taskAccentKey(message);
        var accent = palette.accentFor(tone);
        var bg = palette.panel;
        if (codexTextEquals(tone, "success") || codexTextEquals(tone, "done")) {
            bg = 0x071C10;
        }

        fillPill(dc, bg, x, y, width, height);
        drawTaskIcon(dc, palette, x + 26, y + height / 2, tone, bg);

        var textWidth = width - 66;

        dc.setColor(palette.ink, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x + 52, y + 17, Graphics.FONT_XTINY, fitToPixelWidth(dc, taskPreviewText(message), Graphics.FONT_XTINY, textWidth), Graphics.TEXT_JUSTIFY_LEFT);
    }

    function contextTaskWidth(w, slot) {
        if (slot == 0) {
            return w - 112;
        }
        return w - 86;
    }

    function trimTrailingSpaces(text) {
        var trimmed = text;
        while (trimmed.length() > 0 && codexTextEquals(trimmed.substring(trimmed.length() - 1, trimmed.length()), " ")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        return trimmed;
    }

    function drawWrappedText(dc, text, font, x, y, maxWidth, lineHeight, maxLines, color) {
        var lines = pixelWrappedLines(dc, text, font, maxWidth, maxLines);
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        for (var i = 0; i < lines.size(); i++) {
            dc.drawText(x, y + i * lineHeight, font, lines[i], Graphics.TEXT_JUSTIFY_LEFT);
        }
    }

    function pixelWrappedLines(dc, text, font, maxWidth, maxLines) {
        var cleanText = model.safeString(text);
        var measuringLimit = maxLines * 56;
        if (cleanText.length() > measuringLimit) {
            cleanText = cleanText.substring(0, measuringLimit);
        }
        var lines = [];
        var start = 0;
        while (start < cleanText.length() && lines.size() < maxLines) {
            var endIndex = pixelLineEnd(dc, cleanText, font, start, maxWidth);
            var line = trimTrailingSpaces(cleanText.substring(start, endIndex));
            if (line.length() > 0) {
                lines.add(line);
            }
            start = endIndex;
            while (start < cleanText.length() && codexTextEquals(cleanText.substring(start, start + 1), " ")) {
                start++;
            }
        }
        if (lines.size() == 0) {
            lines.add("");
        }
        return lines;
    }

    function pixelLineEnd(dc, text, font, start, maxWidth) {
        var endIndex = start + 1;
        var best = start + 1;
        var bestWord = -1;

        while (endIndex <= text.length()) {
            var candidate = trimTrailingSpaces(text.substring(start, endIndex));
            if (dc.getTextWidthInPixels(candidate, font) > maxWidth) {
                if (bestWord > start) {
                    return bestWord;
                }
                return best;
            }
            best = endIndex;
            if (endIndex < text.length() && codexTextEquals(text.substring(endIndex - 1, endIndex), " ")) {
                bestWord = endIndex - 1;
            }
            endIndex++;
        }
        return text.length();
    }

    function fitToPixelWidth(dc, text, font, maxWidth) {
        var cleanText = model.safeString(text);
        if (cleanText.length() > 80) {
            cleanText = cleanText.substring(0, 80);
        }
        if (dc.getTextWidthInPixels(cleanText, font) <= maxWidth) {
            return cleanText;
        }

        var endIndex = cleanText.length();
        while (endIndex > 1) {
            var candidate = trimTrailingSpaces(cleanText.substring(0, endIndex));
            if (dc.getTextWidthInPixels(candidate, font) <= maxWidth) {
                return candidate;
            }
            endIndex--;
        }
        return "";
    }

    function taskPreviewText(message) {
        var body = model.safeString(message["body"]);
        if (body.length() > 0) {
            return body;
        }
        return model.taskTitle(message);
    }

    function fillPill(dc, color, x, y, width, height) {
        var radius = height / 2;
        dc.setColor(color, color);
        dc.fillRectangle(x + radius, y, width - height, height);
        dc.fillCircle(x + radius, y + radius, radius);
        dc.fillCircle(x + width - radius, y + radius, radius);
    }

    function drawTaskIcon(dc, palette, cx, cy, tone, bg) {
        var accent = palette.accentFor(tone);
        if (codexTextEquals(tone, "success") || codexTextEquals(tone, "done")) {
            dc.setColor(accent, accent);
            dc.fillCircle(cx, cy, 13);
            dc.setColor(palette.ink, Graphics.COLOR_TRANSPARENT);
            dc.drawLine(cx - 6, cy, cx - 2, cy + 5);
            dc.drawLine(cx - 2, cy + 5, cx + 7, cy - 6);
            return;
        }

        if (codexTextEquals(tone, "review")) {
            dc.setColor(accent, accent);
            dc.fillCircle(cx, cy, 13);
            dc.setColor(bg, bg);
            dc.fillCircle(cx, cy, 10);
            return;
        }

        dc.setColor(accent, accent);
        dc.fillCircle(cx - 11, cy + 6, 3);
        dc.fillRectangle(cx - 5, cy - 2, 4, 13);
        dc.fillRectangle(cx + 2, cy - 10, 4, 21);
        dc.fillCircle(cx + 12, cy - 8, 4);
    }

    function drawTaskDetails(dc, palette, w, h) {
        drawTopTime(dc, palette, w);

        var task = model.selectedTask();
        var subtitle = model.taskSubtitle(task);
        var accent = palette.accentFor(model.taskAccentKey(task));
        var centerX = w / 2;
        var textInset = detailTextInset(w);
        model.setDetailLayout(detailCharsForWidth(w, textInset), detailVisibleLinesForHeight(h));

        dc.setColor(accent, accent);
        dc.fillCircle(centerX - 76, 48, 4);
        dc.setColor(palette.subtle, Graphics.COLOR_TRANSPARENT);
        dc.drawText(centerX, 44, Graphics.FONT_XTINY, fit(subtitle, 24), Graphics.TEXT_JUSTIFY_CENTER);

        dc.setColor(palette.divider, palette.divider);
        dc.fillRectangle(textInset, 64, w - textInset * 2, 1);

        drawScrollableDetails(dc, palette, w, h, accent);
    }

    function drawScrollableDetails(dc, palette, w, h, accent) {
        var x = detailTextInset(w);
        var y = detailTextY(h);
        var lineHeight = detailLineHeight(h);
        var textWidth = w - x * 2 - 8;

        var visibleLines = detailVisibleLinesForHeight(h);
        var lines = pixelWrappedLines(dc, model.detailText(), Graphics.FONT_XTINY, textWidth, 80);
        model.setDetailRenderMetrics(lines.size(), visibleLines);
        for (var i = 0; i < visibleLines; i++) {
            var lineIndex = model.detailScrollLine + i;
            if (lineIndex < lines.size() && lines[lineIndex].length() > 0) {
                dc.setColor(palette.ink, Graphics.COLOR_TRANSPARENT);
                dc.drawText(x, y + i * lineHeight, Graphics.FONT_XTINY, lines[lineIndex], Graphics.TEXT_JUSTIFY_LEFT);
            }
        }

        var count = lines.size();
        if (count > visibleLines) {
            drawScrollRail(dc, palette, w, h, accent, count);
        }
    }

    function drawScrollRail(dc, palette, w, h, accent, count) {
        var railX = w - detailTextInset(w) + 10;
        var railTop = detailTextY(h) + 8;
        var railH = h - railTop - 68;
        dc.setColor(palette.divider, palette.divider);
        dc.fillRectangle(railX, railTop, 2, railH);

        var visibleLines = model.detailVisibleLines();
        var maxScroll = count - visibleLines;
        if (maxScroll < 1) {
            maxScroll = 1;
        }
        var thumbH = (railH * visibleLines) / count;
        if (thumbH < 24) {
            thumbH = 24;
        }
        var thumbY = railTop + ((railH - thumbH) * model.detailScrollLine) / maxScroll;

        dc.setColor(accent, accent);
        dc.fillRectangle(railX - 2, thumbY, 6, thumbH);
    }

    function detailTextInset(w) {
        var inset = w / 9;
        if (inset < 34) {
            inset = 34;
        }
        if (inset > 54) {
            inset = 54;
        }
        return inset;
    }

    function detailCharsForWidth(w, inset) {
        var chars = (w - inset * 2) / 9;
        if (chars < 22) {
            chars = 22;
        }
        if (chars > 44) {
            chars = 44;
        }
        return chars;
    }

    function detailTextY(h) {
        var y = h / 5;
        if (y < 70) {
            y = 70;
        }
        if (y > 88) {
            y = 88;
        }
        return y;
    }

    function detailLineHeight(h) {
        var lineHeight = h / 15;
        if (lineHeight < 23) {
            lineHeight = 23;
        }
        if (lineHeight > 27) {
            lineHeight = 27;
        }
        return lineHeight;
    }

    function detailVisibleLinesForHeight(h) {
        var lines = (h - detailTextY(h) - 54) / detailLineHeight(h);
        if (lines < 5) {
            lines = 5;
        }
        if (lines > 11) {
            lines = 11;
        }
        return lines;
    }

    function drawPageDots(dc, palette, w, h, active) {
        var y = h - 34;
        var startX = w / 2 - 16;
        for (var i = 0; i < 3; i++) {
            var color = i == active ? palette.accent : palette.subtle;
            dc.setColor(color, color);
            dc.fillCircle(startX + i * 16, y, i == active ? 4 : 3);
        }
    }

    function drawTaskPositionDots(dc, palette, w, h) {
        var count = model.taskCount();
        if (count <= 1) {
            return;
        }
        var dots = count;
        if (dots > 5) {
            dots = 5;
        }
        var selected = model.selectedTaskIndex;
        if (selected < 0) {
            selected = 0;
        }
        if (selected >= count) {
            selected = count - 1;
        }
        var activeDot = selected;
        if (count > dots && count > 1) {
            activeDot = (selected * (dots - 1)) / (count - 1);
        }

        var y = h - 34;
        var spacing = 9;
        var startX = w / 2 - ((dots - 1) * spacing) / 2;
        for (var i = 0; i < dots; i++) {
            var color = i == activeDot ? palette.accent : palette.subtle;
            dc.setColor(color, color);
            dc.fillCircle(startX + i * spacing, y, i == activeDot ? 3 : 2);
        }
    }

    function homeStatusText() {
        if (model.hasNetworkError) {
            return model.status;
        }
        if (!model.hasSeenTaskPayload) {
            return "Waiting for bridge";
        }
        return model.summary;
    }

    function fit(value, maxChars) {
        var text = model.safeString(value);
        if (text.length() <= maxChars) {
            return text;
        }
        return text.substring(0, maxChars - 1) + "...";
    }
}
