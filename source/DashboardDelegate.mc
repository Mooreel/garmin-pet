using Toybox.WatchUi;

class DashboardDelegate extends WatchUi.BehaviorDelegate {
    var model;

    function initialize(modelRef) {
        BehaviorDelegate.initialize();
        model = modelRef;
    }

    function onSelect() {
        if (model.isPetScreen() || model.isTaskOverview()) {
            model.advanceScreen();
            WatchUi.requestUpdate();
            return true;
        }

        return false;
    }

    function onMenu() {
        model.refresh();
        return true;
    }

    function onBack() {
        if (model.backScreen()) {
            WatchUi.requestUpdate();
            return true;
        }
        return false;
    }

    function onNextPage() {
        if (model.isTaskOverview()) {
            model.nextTask();
            WatchUi.requestUpdate();
            return true;
        }
        if (model.isTaskDetails()) {
            model.scrollDetailsDown();
            WatchUi.requestUpdate();
            return true;
        }
        return false;
    }

    function onPreviousPage() {
        if (model.isTaskOverview()) {
            model.previousTask();
            WatchUi.requestUpdate();
            return true;
        }
        if (model.isTaskDetails()) {
            model.scrollDetailsUp();
            WatchUi.requestUpdate();
            return true;
        }
        return false;
    }

    function onTap(clickEvent) {
        if (model.isPetScreen()) {
            model.triggerPetJump();
            WatchUi.requestUpdate();
            return true;
        }

        if (model.isTaskOverview()) {
            var coordinates = clickEvent.getCoordinates();
            var y = coordinates[1];
            var slot = -1;
            if (y >= 44 && y < 98) {
                slot = 0;
            } else if (y >= 104 && y < 202) {
                slot = 1;
            } else if (y >= 212 && y < 266) {
                slot = 2;
            }
            if (slot >= 0 && slot < 3 && model.selectOverviewTaskSlot(slot)) {
                model.advanceScreen();
                WatchUi.requestUpdate();
                return true;
            }
        }

        if (model.isTaskDetails()) {
            var detailCoordinates = clickEvent.getCoordinates();
            if (detailCoordinates[1] < 180) {
                model.scrollDetailsUp();
            } else {
                model.scrollDetailsDown();
            }
            WatchUi.requestUpdate();
            return true;
        }

        return onSelect();
    }

    function onSwipe(swipeEvent) {
        var direction = swipeEvent.getDirection();
        if (direction == WatchUi.SWIPE_UP || direction == WatchUi.SWIPE_LEFT) {
            return onNextPage();
        }
        if (direction == WatchUi.SWIPE_DOWN || direction == WatchUi.SWIPE_RIGHT) {
            return onPreviousPage();
        }
        return false;
    }
}
