using Toybox.System;
using Toybox.Test;

(:test)
function testTaskCompleteIsDoneAndSortedLast(logger) {
    var model = new CodexStateModel();
    model.hasSeenTaskPayload = true;

    var complete = {
        "title" => "Codex done",
        "body" => "Task complete",
        "tone" => "success",
        "eventType" => "task_complete",
        "time" => "01:00"
    };
    var active = {
        "title" => "Task started",
        "body" => "Working on app changes",
        "tone" => "review",
        "eventType" => "agent_message",
        "time" => "01:01"
    };

    var ordered = model.orderMessages([complete, active]);
    Test.assertEqual("Task started", ordered[0]["title"]);
    Test.assertEqual("Codex done", ordered[1]["title"]);
    Test.assertEqual("Done", model.taskStatus(complete));
    Test.assertEqual("success", model.taskAccentKey(complete));
    return true;
}

(:test)
function testTaskListKeepsOpenAndLastTwoDone(logger) {
    var model = new CodexStateModel();
    model.hasSeenTaskPayload = true;

    var active1 = { "title" => "Open 1", "body" => "First open task", "tone" => "review", "eventType" => "agent_message" };
    var done1 = { "title" => "Done 1", "body" => "Task complete", "tone" => "success", "eventType" => "task_complete" };
    var active2 = { "title" => "Open 2", "body" => "Second open task", "tone" => "review", "eventType" => "agent_message" };
    var done2 = { "title" => "Done 2", "body" => "Task complete", "tone" => "success", "eventType" => "task_complete" };
    var done3 = { "title" => "Done 3", "body" => "Task complete", "tone" => "success", "eventType" => "task_complete" };

    var ordered = model.orderMessages([active1, done1, active2, done2, done3]);
    Test.assertEqual(4, ordered.size());
    Test.assertEqual("Open 1", ordered[0]["title"]);
    Test.assertEqual("Open 2", ordered[1]["title"]);
    Test.assertEqual("Done 1", ordered[2]["title"]);
    Test.assertEqual("Done 2", ordered[3]["title"]);
    return true;
}

(:test)
function testTaskOverviewCentersSelectedTask(logger) {
    var model = new CodexStateModel();
    model.messages = [
        { "title" => "Open 1", "body" => "Task one", "tone" => "review" },
        { "title" => "Open 2", "body" => "Task two", "tone" => "review" },
        { "title" => "Open 3", "body" => "Task three", "tone" => "review" }
    ];
    model.selectedTaskIndex = 0;

    Test.assertEqual(-1, model.overviewTaskIndexForSlot(0));
    Test.assertEqual(0, model.overviewTaskIndexForSlot(1));
    Test.assertEqual(1, model.overviewTaskIndexForSlot(2));

    model.nextTask();
    Test.assertEqual(0, model.overviewTaskIndexForSlot(0));
    Test.assertEqual(1, model.overviewTaskIndexForSlot(1));
    Test.assertEqual(2, model.overviewTaskIndexForSlot(2));
    return true;
}

(:test)
function testAnimationFrameAdvancesFromElapsedTime(logger) {
    var view = new DashboardView(new CodexStateModel());
    view.largePetFrames = [0, 1, 2, 3, 4, 5, 6, 7];
    view.loadedPetState = "running";
    view.frame = 0;
    view.frameStartedMs = System.getTimer() - 400;

    view.updateAnimationFrame();

    Test.assert(view.frame > 0);
    Test.assert(view.frame < view.largePetFrames.size());
    return true;
}

(:test)
function testRuntimePetStateUsesReviewForRunning(logger) {
    var model = new CodexStateModel();
    model.petState = "running";

    var view = new DashboardView(model);
    view.syncPetFrames();

    Test.assertEqual("review", view.loadedPetState);
    Test.assertEqual(8, view.largePetFrames.size());
    view.frameStartedMs = System.getTimer() - 400;
    view.updateAnimationFrame();
    Test.assert(view.frame > 0);
    return true;
}
