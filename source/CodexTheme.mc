using Toybox.Graphics;

class CodexTheme {
    var dc;
    var surface;
    var panel;
    var selection;
    var divider;
    var ink;
    var subtle;
    var accent;
    var cyan;
    var good;
    var warn;
    var review;

    function initialize(drawContext) {
        var settings = new CodexSettings();
        dc = drawContext;
        surface = settings.colorSurface();
        panel = settings.colorPanel();
        selection = settings.colorSelection();
        divider = 0x2A2C35;
        ink = settings.colorInk();
        subtle = settings.colorSubtle();
        accent = settings.colorAccent();
        cyan = settings.colorReview();
        good = settings.colorGood();
        warn = settings.colorWarn();
        review = cyan;
    }

    function clear() {
        dc.setColor(surface, surface);
        dc.clear();
    }

    function accentFor(tone) {
        if (codexTextEquals(tone, "warning") || codexTextEquals(tone, "blocked")) {
            return warn;
        }
        if (codexTextEquals(tone, "review")) {
            return review;
        }
        if (codexTextEquals(tone, "running")) {
            return accent;
        }
        if (codexTextEquals(tone, "done") || codexTextEquals(tone, "success")) {
            return good;
        }
        return accent;
    }
}
