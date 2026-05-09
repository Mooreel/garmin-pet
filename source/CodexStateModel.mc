using Toybox.Application;
using Toybox.Attention;
using Toybox.Communications;
using Toybox.Lang;
using Toybox.PersistedContent;
using Toybox.System;
using Toybox.WatchUi;

class CodexStateModel {
    const SCREEN_PET = 0;
    const SCREEN_TASKS = 1;
    const SCREEN_DETAILS = 2;
    const DEFAULT_DETAIL_CHARS = 34;
    const DEFAULT_DETAIL_VISIBLE_LINES = 9;

    var settings;
    var endpoint;
    var summary;
    var mood;
    var status;
    var petName;
    var petState;
    var progress;
    var updatedAt;
    var messages;
    var hasNetworkError;
    var isLoading;
    var lastRequestMs;
    var autoRefresh;
    var hapticAlerts;
    var currentScreen;
    var selectedTaskIndex;
    var detailScrollLine;
    var detailChars;
    var detailVisibleLineCount;
    var detailRenderedLineCount;
    var petJumpUntilMs;
    var hasSeenTaskPayload;
    var lastTaskFingerprint;
    var lastVibeFingerprint;
    var lastVibeMs;

    function initialize() {
        settings = new CodexSettings();
        endpoint = loadEndpoint();
        autoRefresh = loadAutoRefresh();
        hapticAlerts = loadHapticAlerts();
        summary = "Codex is waiting";
        mood = "idle";
        status = "Open the bridge";
        petName = settings.petName();
        petState = "idle";
        progress = 0;
        updatedAt = "--:--";
        messages = [
            { :title => "Codex Pet", :body => "Start the bridge to stream live Codex work.", :tone => "info", :time => "" }
        ];
        hasNetworkError = false;
        isLoading = false;
        lastRequestMs = 0;
        currentScreen = SCREEN_PET;
        selectedTaskIndex = 0;
        detailScrollLine = 0;
        detailChars = DEFAULT_DETAIL_CHARS;
        detailVisibleLineCount = DEFAULT_DETAIL_VISIBLE_LINES;
        detailRenderedLineCount = 0;
        petJumpUntilMs = 0;
        hasSeenTaskPayload = false;
        lastTaskFingerprint = "";
        lastVibeFingerprint = "";
        lastVibeMs = 0;
    }

    function loadEndpoint() {
        return settings.bridgeUrl();
    }

    function loadAutoRefresh() {
        return settings.autoRefresh();
    }

    function loadHapticAlerts() {
        return settings.hapticAlerts();
    }

    function reloadSettings() {
        endpoint = loadEndpoint();
        autoRefresh = loadAutoRefresh();
        hapticAlerts = loadHapticAlerts();
    }

    function refresh() {
        reloadSettings();
        var now = System.getTimer();
        if (isLoading || (now - lastRequestMs < 3000)) {
            return;
        }

        isLoading = true;
        lastRequestMs = now;

        var options = {
            :method => Communications.HTTP_REQUEST_METHOD_GET,
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };

        Communications.makeWebRequest(endpoint, {}, options, method(:onResponse));
    }

    function onResponse(responseCode as Lang.Number, data as Lang.Dictionary or Lang.String or PersistedContent.Iterator or Null) as Void {
        isLoading = false;

        if (responseCode != 200 || data == null || !(data instanceof Lang.Dictionary)) {
            hasNetworkError = true;
            status = "Bridge " + responseCode;
            messages = [
                { :title => "Bridge offline", :body => bridgeErrorText(responseCode), :tone => "warning", :time => "" }
            ];
            resetDetailRenderMetrics();
            WatchUi.requestUpdate();
            return;
        }

        var previousFingerprint = hapticFingerprint();
        var wasTracking = hasSeenTaskPayload;
        hasNetworkError = false;
        applyPayload(data);
        lastTaskFingerprint = hapticFingerprint();
        if (wasTracking && lastTaskFingerprint.length() > 0 && previousFingerprint != lastTaskFingerprint) {
            playTaskVibration(currentVibrationKind(), lastTaskFingerprint);
        }
        hasSeenTaskPayload = true;
        WatchUi.requestUpdate();
    }

    function applyPayload(data) {
        summary = valueOr(data, "summary", summary);
        mood = valueOr(data, "mood", mood);
        status = valueOr(data, "status", status);
        updatedAt = valueOr(data, "updatedAt", updatedAt);

        var rawProgress = data["progress"];
        if (rawProgress != null) {
            progress = rawProgress;
        }

        var pet = data["pet"];
        if (pet != null) {
            petName = valueOr(pet, "displayName", petName);
            petState = valueOr(pet, "state", petState);
        }

        var incoming = data["messages"];
        if (incoming != null && incoming.size() > 0) {
            messages = orderMessages(incoming);
            resetDetailRenderMetrics();
        }
        clampSelectedTask();
        clampDetailScroll();
    }

    function orderMessages(incoming) {
        var active = [];
        var done = [];
        for (var i = 0; i < incoming.size(); i++) {
            var message = incoming[i];
            if (isDoneMessage(message)) {
                if (done.size() < 2) {
                    done.add(message);
                }
            } else {
                active.add(message);
            }
        }

        for (var j = 0; j < done.size(); j++) {
            active.add(done[j]);
        }
        return active;
    }

    function valueOr(dict, key, fallback) {
        var value = dict[key];
        if (value == null) {
            return fallback;
        }
        return value;
    }

    function bridgeErrorText(responseCode) {
        if (responseCode == -104) {
            return "Watch is not connected to the phone over Bluetooth. Open Garmin Connect and sync.";
        }
        if (responseCode == -300) {
            return "Bridge timed out. Rebuild app, then check iPhone WiFi and Local Network.";
        }
        if (responseCode == -400) {
            return "Phone connection unavailable. Open Garmin Connect and keep watch paired.";
        }
        if (responseCode < 0) {
            return "Connect IQ network error " + responseCode + " to " + compactText(endpoint, 26);
        }
        return "HTTP " + responseCode + " from " + compactText(endpoint, 26);
    }

    function topMessage() {
        if (messages == null || messages.size() == 0) {
            return { :title => "Codex", :body => "No messages yet.", :tone => "info", :time => "" };
        }
        return messages[0];
    }

    function taskCount() {
        if (messages == null) {
            return 0;
        }
        return messages.size();
    }

    function runningTaskCount() {
        if (!hasSeenTaskPayload || hasNetworkError) {
            return 0;
        }

        var count = 0;
        for (var i = 0; i < taskCount(); i++) {
            var statusText = taskStatus(taskAt(i));
            if (!codexTextEquals(statusText, "Done") && !codexTextEquals(statusText, "Offline")) {
                count++;
            }
        }
        if (count > 9) {
            return 9;
        }
        return count;
    }

    function taskAt(index) {
        var count = taskCount();
        if (count == 0) {
            return { :title => "Codex Pet", :body => "No task updates yet.", :tone => "info", :time => "" };
        }
        if (index < 0) {
            index = 0;
        }
        if (index >= count) {
            index = count - 1;
        }
        return messages[index];
    }

    function selectedTask() {
        clampSelectedTask();
        return taskAt(selectedTaskIndex);
    }

    function detailUpdateAt(offset) {
        var count = taskCount();
        if (count == 0) {
            return null;
        }

        var index = selectedTaskIndex + offset;
        if (index >= count) {
            return null;
        }
        return taskAt(index);
    }

    function taskTitle(message) {
        var title = safeString(message["title"]);
        var body = safeString(message["body"]);
        if (isBridgeEventTitle(title)) {
            if (body.length() > 0) {
                return compactText(body, 28);
            }
            return "Codex task";
        }
        return compactText(title, 28);
    }

    function taskAccentKey(message) {
        var statusText = taskStatus(message);
        if (codexTextEquals(statusText, "Done")) {
            return "success";
        }
        if (codexTextEquals(statusText, "Attention") || codexTextEquals(statusText, "Offline")) {
            return "warning";
        }
        if (codexTextEquals(statusText, "Running")) {
            return "running";
        }
        return "review";
    }

    function taskStatus(message) {
        if (isDoneMessage(message)) {
            return "Done";
        }
        if (!hasSeenTaskPayload) {
            return "Waiting";
        }
        if (hasNetworkError) {
            return "Offline";
        }

        var title = safeString(message["title"]);
        var tone = safeString(message["tone"]);
        if (codexTextEquals(tone, "warning") || codexTextEquals(tone, "blocked")) {
            return "Attention";
        }
        if (codexTextEquals(tone, "review")) {
            return "Update";
        }
        if (isBridgeEventTitle(title)) {
            return "Update";
        }
        return "Running";
    }

    function isDoneMessage(message) {
        var title = safeString(message["title"]);
        var body = safeString(message["body"]);
        var tone = safeString(message["tone"]);
        var eventType = safeString(message["eventType"]);

        if (codexTextEquals(tone, "success") || codexTextEquals(tone, "done") || codexTextEquals(title, "Codex done") || codexTextEquals(eventType, "task_complete") || codexTextEquals(eventType, "final_answer")) {
            return true;
        }
        if (looksDoneText(title)) {
            return true;
        }
        if (looksDoneText(body)) {
            return true;
        }
        return false;
    }

    function looksDoneText(value) {
        var text = safeString(value);
        if (codexTextEquals(text, "Task done") || codexTextEquals(text, "Task done.") || codexTextEquals(text, "Task complete") || codexTextEquals(text, "Task complete.") || codexTextEquals(text, "Task completed") || codexTextEquals(text, "Task completed.") || codexTextEquals(text, "Task finished") || codexTextEquals(text, "Task finished.") || codexTextEquals(text, "Done") || codexTextEquals(text, "Done.")) {
            return true;
        }
        if (codexTextStartsWith(text, "Task done")) {
            return true;
        }
        if (codexTextStartsWith(text, "Task complete")) {
            return true;
        }
        if (codexTextStartsWith(text, "Task finished")) {
            return true;
        }
        return false;
    }

    function taskSubtitle(message) {
        var time = safeString(message["time"]);
        var state = taskStatus(message);
        if (time.length() > 0) {
            return time + "  " + state;
        }
        return state;
    }

    function detailText() {
        var task = selectedTask();
        var body = safeString(task["body"]);
        if (body.length() > 0) {
            return body;
        }
        return taskTitle(task);
    }

    function detailLineCount() {
        if (detailRenderedLineCount > 0) {
            return detailRenderedLineCount;
        }

        var text = detailText();
        if (text.length() == 0) {
            return 1;
        }

        var count = 0;
        var start = 0;
        while (start < text.length()) {
            count++;
            start = detailNextLineStart(text, start);
        }
        if (count < 1) {
            count = 1;
        }
        return count;
    }

    function detailLineAt(lineIndex) {
        var text = detailText();
        if (text.length() == 0) {
            return "";
        }

        var start = 0;
        for (var i = 0; i < lineIndex; i++) {
            start = detailNextLineStart(text, start);
        }
        if (start >= text.length()) {
            return "";
        }
        var endIndex = detailLineEnd(text, start);
        return text.substring(start, endIndex);
    }

    function detailNextLineStart(text, start) {
        var next = detailLineEnd(text, start);
        while (next < text.length() && text.substring(next, next + 1).equals(" ")) {
            next++;
        }
        return next;
    }

    function detailLineEnd(text, start) {
        var endIndex = start + detailChars;
        if (endIndex >= text.length()) {
            return text.length();
        }

        var minWordWrap = start + (detailChars / 2);
        if (minWordWrap < start + 10) {
            minWordWrap = start + 10;
        }
        for (var i = endIndex; i > minWordWrap; i--) {
            if (text.substring(i - 1, i).equals(" ")) {
                return i - 1;
            }
        }
        return endIndex;
    }

    function setDetailRenderMetrics(lineCount, visibleLines) {
        if (lineCount < 1) {
            lineCount = 1;
        }
        detailRenderedLineCount = lineCount;
        setDetailLayout(detailChars, visibleLines);
    }

    function resetDetailRenderMetrics() {
        detailRenderedLineCount = 0;
    }

    function setDetailLayout(chars, visibleLines) {
        if (chars < 22) {
            chars = 22;
        }
        if (chars > 44) {
            chars = 44;
        }
        if (visibleLines < 5) {
            visibleLines = 5;
        }
        if (visibleLines > 11) {
            visibleLines = 11;
        }

        var changed = chars != detailChars || visibleLines != detailVisibleLineCount;
        detailChars = chars;
        detailVisibleLineCount = visibleLines;
        if (changed) {
            clampDetailScroll();
        }
    }

    function detailVisibleLines() {
        return detailVisibleLineCount;
    }

    function petAnimationState() {
        var now = System.getTimer();
        if (petJumpUntilMs != 0) {
            if (now < petJumpUntilMs) {
                return "jumping";
            }
            petJumpUntilMs = 0;
        }

        var state = safeString(petState);
        if (codexTextEquals(state, "running") || codexTextEquals(state, "working") || codexTextEquals(state, "listening")) {
            return "review";
        }
        if (codexTextEquals(state, "waving") || codexTextEquals(state, "jumping") || codexTextEquals(state, "failed") || codexTextEquals(state, "review") || codexTextEquals(state, "sleeping")) {
            return state;
        }
        if (codexTextEquals(safeString(mood), "working")) {
            return "review";
        }
        return "idle";
    }

    function triggerPetJump() {
        petJumpUntilMs = System.getTimer() + 1700;
    }

    function scrollDetailsDown() {
        detailScrollLine += detailVisibleLineCount - 1;
        clampDetailScroll();
    }

    function scrollDetailsUp() {
        detailScrollLine -= detailVisibleLineCount - 1;
        clampDetailScroll();
    }

    function clampDetailScroll() {
        if (detailScrollLine < 0) {
            detailScrollLine = 0;
        }
        var maxScroll = detailLineCount() - detailVisibleLineCount;
        if (maxScroll < 0) {
            maxScroll = 0;
        }
        if (detailScrollLine > maxScroll) {
            detailScrollLine = maxScroll;
        }
    }

    function isBridgeEventTitle(title) {
        return title.length() == 0
            || codexTextEquals(title, "Codex")
            || codexTextEquals(title, "Codex done")
            || codexTextEquals(title, "Codex Pet")
            || codexTextEquals(title, "You")
            || codexTextEquals(title, "Bridge offline");
    }

    function compactText(value, maxChars) {
        var text = safeString(value);
        if (text.length() <= maxChars) {
            return text;
        }
        return text.substring(0, maxChars - 1) + "...";
    }

    function isPetScreen() {
        return currentScreen == SCREEN_PET;
    }

    function isTaskOverview() {
        return currentScreen == SCREEN_TASKS;
    }

    function isTaskDetails() {
        return currentScreen == SCREEN_DETAILS;
    }

    function advanceScreen() {
        if (isPetScreen()) {
            currentScreen = SCREEN_TASKS;
            selectedTaskIndex = 0;
            detailScrollLine = 0;
            clampSelectedTask();
            return true;
        }
        if (isTaskOverview()) {
            currentScreen = SCREEN_DETAILS;
            clampSelectedTask();
            detailScrollLine = 0;
            return true;
        }
        refresh();
        return true;
    }

    function backScreen() {
        if (isTaskDetails()) {
            currentScreen = SCREEN_TASKS;
            return true;
        }
        if (isTaskOverview()) {
            currentScreen = SCREEN_PET;
            return true;
        }
        return false;
    }

    function nextTask() {
        var count = taskCount();
        if (count == 0) {
            return;
        }
        selectedTaskIndex++;
        if (selectedTaskIndex >= count) {
            selectedTaskIndex = count - 1;
        }
        detailScrollLine = 0;
        resetDetailRenderMetrics();
    }

    function previousTask() {
        selectedTaskIndex--;
        if (selectedTaskIndex < 0) {
            selectedTaskIndex = 0;
        }
        detailScrollLine = 0;
        resetDetailRenderMetrics();
    }

    function overviewTaskIndexForSlot(slot) {
        var count = taskCount();
        if (count == 0) {
            return -1;
        }

        clampSelectedTask();
        if (slot == 1) {
            return selectedTaskIndex;
        }
        if (slot == 0) {
            if (selectedTaskIndex > 0) {
                return selectedTaskIndex - 1;
            }
            return -1;
        }
        if (slot == 2) {
            if (selectedTaskIndex < count - 1) {
                return selectedTaskIndex + 1;
            }
            return -1;
        }
        return -1;
    }

    function selectOverviewTaskSlot(slot) {
        var index = overviewTaskIndexForSlot(slot);
        if (index < 0) {
            return false;
        }
        selectedTaskIndex = index;
        detailScrollLine = 0;
        resetDetailRenderMetrics();
        return true;
    }

    function clampSelectedTask() {
        var count = taskCount();
        if (count == 0) {
            selectedTaskIndex = 0;
            resetDetailRenderMetrics();
            return;
        }
        if (selectedTaskIndex < 0) {
            selectedTaskIndex = 0;
        }
        if (selectedTaskIndex >= count) {
            selectedTaskIndex = count - 1;
        }
    }

    function taskFingerprint() {
        var message = topMessage();
        return safeString(status)
            + "|"
            + safeString(mood)
            + "|"
            + safeString(progress)
            + "|"
            + safeString(message["title"])
            + "|"
            + safeString(message["body"])
            + "|"
            + safeString(message["tone"]);
    }

    function hapticFingerprint() {
        var message = hapticMessage();
        if (message == null) {
            return "";
        }

        var alertId = safeString(message["alertId"]);
        if (alertId.length() > 0) {
            return alertId;
        }

        return safeString(message["eventType"])
            + "|"
            + safeString(message["title"])
            + "|"
            + safeString(message["body"])
            + "|"
            + safeString(message["tone"])
            + "|"
            + safeString(message["time"]);
    }

    function hapticMessage() {
        if (messages == null) {
            return null;
        }
        for (var i = 0; i < messages.size(); i++) {
            var message = messages[i];
            if (isHapticMessage(message)) {
                return message;
            }
        }
        return null;
    }

    function isHapticMessage(message) {
        var alert = message["alert"];
        if (alert == true) {
            return true;
        }
        var text = safeString(alert);
        return codexTextEquals(text, "true") || codexTextEquals(text, "1");
    }

    function safeString(value) {
        if (value == null) {
            return "";
        }
        return value.toString();
    }

    function currentVibrationKind() {
        var message = hapticMessage();
        if (message == null) {
            return "update";
        }
        var tone = safeString(message["tone"]);
        if (codexTextEquals(tone, "success")) {
            return "success";
        }
        if (codexTextEquals(tone, "warning")) {
            return "warning";
        }
        return "update";
    }

    function playTaskVibration(kind, fingerprint) {
        if (!hapticAlerts || !(Attention has :vibrate)) {
            return;
        }
        if (codexTextEquals(fingerprint, lastVibeFingerprint)) {
            return;
        }

        var now = System.getTimer();
        var minGap = 12000;
        if (codexTextEquals(kind, "success") || codexTextEquals(kind, "warning")) {
            minGap = 3000;
        }
        if (lastVibeMs != 0 && now - lastVibeMs < minGap) {
            return;
        }

        var vibeData = [
            new Attention.VibeProfile(55, 120)
        ];
        if (codexTextEquals(kind, "success")) {
            vibeData = [
                new Attention.VibeProfile(75, 110),
                new Attention.VibeProfile(0, 80),
                new Attention.VibeProfile(75, 170)
            ];
        } else if (codexTextEquals(kind, "warning")) {
            vibeData = [
                new Attention.VibeProfile(90, 240)
            ];
        }

        Attention.vibrate(vibeData);
        lastVibeMs = now;
        lastVibeFingerprint = fingerprint;
    }

    function toggleMessageFocus() {
        if (isPetScreen()) {
            currentScreen = SCREEN_TASKS;
        } else {
            currentScreen = SCREEN_PET;
        }
    }
}
