using Toybox.Application;
using Toybox.Lang;
using Toybox.WatchUi;

class CodexPetApp extends Application.AppBase {
    function initialize() {
        AppBase.initialize();
    }

    function getInitialView() {
        var model = new CodexStateModel();
        return [ new DashboardView(model), new DashboardDelegate(model) ];
    }
}
