using Toybox.WatchUi;

class CodexPetSprites {
    function framesFor(state) {
        if (codexTextEquals(state, "waving")) {
            return [
                WatchUi.loadResource(Rez.Drawables.PetLargeWavingFrame0),
                WatchUi.loadResource(Rez.Drawables.PetLargeWavingFrame1),
                WatchUi.loadResource(Rez.Drawables.PetLargeWavingFrame2),
                WatchUi.loadResource(Rez.Drawables.PetLargeWavingFrame3),
                WatchUi.loadResource(Rez.Drawables.PetLargeWavingFrame4),
                WatchUi.loadResource(Rez.Drawables.PetLargeWavingFrame5),
                WatchUi.loadResource(Rez.Drawables.PetLargeWavingFrame6),
                WatchUi.loadResource(Rez.Drawables.PetLargeWavingFrame7)
            ];
        }

        if (codexTextEquals(state, "jumping")) {
            return [
                WatchUi.loadResource(Rez.Drawables.PetLargeJumpingFrame0),
                WatchUi.loadResource(Rez.Drawables.PetLargeJumpingFrame1),
                WatchUi.loadResource(Rez.Drawables.PetLargeJumpingFrame2),
                WatchUi.loadResource(Rez.Drawables.PetLargeJumpingFrame3),
                WatchUi.loadResource(Rez.Drawables.PetLargeJumpingFrame4),
                WatchUi.loadResource(Rez.Drawables.PetLargeJumpingFrame5),
                WatchUi.loadResource(Rez.Drawables.PetLargeJumpingFrame6),
                WatchUi.loadResource(Rez.Drawables.PetLargeJumpingFrame7)
            ];
        }

        if (codexTextEquals(state, "failed")) {
            return [
                WatchUi.loadResource(Rez.Drawables.PetLargeFailedFrame0),
                WatchUi.loadResource(Rez.Drawables.PetLargeFailedFrame1),
                WatchUi.loadResource(Rez.Drawables.PetLargeFailedFrame2),
                WatchUi.loadResource(Rez.Drawables.PetLargeFailedFrame3),
                WatchUi.loadResource(Rez.Drawables.PetLargeFailedFrame4),
                WatchUi.loadResource(Rez.Drawables.PetLargeFailedFrame5),
                WatchUi.loadResource(Rez.Drawables.PetLargeFailedFrame6),
                WatchUi.loadResource(Rez.Drawables.PetLargeFailedFrame7)
            ];
        }

        if (codexTextEquals(state, "review")) {
            return [
                WatchUi.loadResource(Rez.Drawables.PetLargeReviewFrame0),
                WatchUi.loadResource(Rez.Drawables.PetLargeReviewFrame1),
                WatchUi.loadResource(Rez.Drawables.PetLargeReviewFrame2),
                WatchUi.loadResource(Rez.Drawables.PetLargeReviewFrame3),
                WatchUi.loadResource(Rez.Drawables.PetLargeReviewFrame4),
                WatchUi.loadResource(Rez.Drawables.PetLargeReviewFrame5),
                WatchUi.loadResource(Rez.Drawables.PetLargeReviewFrame6),
                WatchUi.loadResource(Rez.Drawables.PetLargeReviewFrame7)
            ];
        }

        if (codexTextEquals(state, "sleeping")) {
            return [
                WatchUi.loadResource(Rez.Drawables.PetLargeSleepingFrame0),
                WatchUi.loadResource(Rez.Drawables.PetLargeSleepingFrame1),
                WatchUi.loadResource(Rez.Drawables.PetLargeSleepingFrame2),
                WatchUi.loadResource(Rez.Drawables.PetLargeSleepingFrame3),
                WatchUi.loadResource(Rez.Drawables.PetLargeSleepingFrame4),
                WatchUi.loadResource(Rez.Drawables.PetLargeSleepingFrame5),
                WatchUi.loadResource(Rez.Drawables.PetLargeSleepingFrame6),
                WatchUi.loadResource(Rez.Drawables.PetLargeSleepingFrame7)
            ];
        }

        return [
            WatchUi.loadResource(Rez.Drawables.PetLargeIdleFrame0),
            WatchUi.loadResource(Rez.Drawables.PetLargeIdleFrame1),
            WatchUi.loadResource(Rez.Drawables.PetLargeIdleFrame2),
            WatchUi.loadResource(Rez.Drawables.PetLargeIdleFrame3),
            WatchUi.loadResource(Rez.Drawables.PetLargeIdleFrame4),
            WatchUi.loadResource(Rez.Drawables.PetLargeIdleFrame5),
            WatchUi.loadResource(Rez.Drawables.PetLargeIdleFrame6),
            WatchUi.loadResource(Rez.Drawables.PetLargeIdleFrame7)
        ];
    }

    function frameInterval(state) {
        if (codexTextEquals(state, "jumping")) {
            return 180;
        }
        if (codexTextEquals(state, "waving") || codexTextEquals(state, "review") || codexTextEquals(state, "failed")) {
            return 240;
        }
        return 360;
    }
}
