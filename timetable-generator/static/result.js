document.addEventListener("DOMContentLoaded", function () {
    var searchInput = document.getElementById("result-search");
    var kindSelect = document.getElementById("result-kind");
    var clearButton = document.getElementById("clear-result-search");
    var counter = document.getElementById("result-search-count");
    var emptyMessage = document.getElementById("result-search-empty");
    var cards = Array.prototype.slice.call(document.querySelectorAll("[data-result-card]"));

    var exportOptionsNode = document.getElementById("export-options-json");
    var exportForm = document.getElementById("export-filter-form");
    var exportViewKind = document.getElementById("export-view-kind");
    var exportSelectionMode = document.getElementById("export-selection-mode");
    var exportFormat = document.getElementById("export-format");
    var exportTargets = document.getElementById("export-targets");
    var exportTargetWrap = document.getElementById("export-target-wrap");
    var exportTargetHint = document.getElementById("export-target-hint");
    var exportOptions = { section: [], class: [], faculty: [], room: [] };

    var manualEditForm = document.getElementById("manual-edit-form");
    var manualEditSource = document.getElementById("manual-edit-source");
    var manualEditSectionWrap = document.getElementById("manual-edit-section-wrap");
    var manualEditSection = document.getElementById("manual-edit-section");
    var manualEditFacultyWrap = document.getElementById("manual-edit-faculty-wrap");
    var manualEditFaculty = document.getElementById("manual-edit-faculty");
    var manualEditDay = document.getElementById("manual-edit-day");
    var manualEditPeriod = document.getElementById("manual-edit-period");
    var manualEditAction = document.getElementById("manual-edit-action");
    var manualEditSetClear = document.getElementById("manual-edit-set-clear");
    var manualEditDetailFields = document.getElementById("manual-edit-detail-fields");
    var manualEditSubject = document.getElementById("manual-edit-subject");
    var manualEditTeacher = document.getElementById("manual-edit-teacher");
    var manualEditRoom = document.getElementById("manual-edit-room");
    var manualEditSelectionSummary = document.getElementById("manual-edit-selection-summary");
    var manualEditLiveWarning = document.getElementById("manual-edit-live-warning");
    var manualEditSourceSectionHidden = document.getElementById("manual-edit-source-section-key");
    var manualEditSourceDayHidden = document.getElementById("manual-edit-source-day");
    var manualEditSourcePeriodHidden = document.getElementById("manual-edit-source-period");
    var manualEditSlotCells = Array.prototype.slice.call(
        document.querySelectorAll(".manual-slot-cell[data-slot-editable='1']")
    );
    var manualSlotActionBar = document.getElementById("manual-slot-action-bar");
    var manualSlotActionTitle = document.getElementById("manual-slot-action-title");
    var manualSlotActionClear = document.getElementById("manual-slot-action-clear");
    var manualSlotActionTheory = document.getElementById("manual-slot-action-theory");
    var manualSlotActionLab = document.getElementById("manual-slot-action-lab");
    var manualSlotActionLock = document.getElementById("manual-slot-action-lock");
    var manualSlotActionUnlock = document.getElementById("manual-slot-action-unlock");
    var manualSlotActionClose = document.getElementById("manual-slot-action-close");
    var selectedManualEditCell = null;
    var selectedManualSlotData = null;
    var draggingManualSlotCell = null;
    var draggingManualSlotData = null;
    var syncManualEditSource = function () {};
    var syncManualEditAction = function () {};

    function normalize(value) {
        return String(value || "")
            .toLowerCase()
            .replace(/\s+/g, " ")
            .trim();
    }

    function safeParseExportOptions() {
        if (!exportOptionsNode) {
            return;
        }

        try {
            var parsed = JSON.parse(exportOptionsNode.textContent || "{}");
            if (parsed && typeof parsed === "object") {
                exportOptions = {
                    section: Array.isArray(parsed.section) ? parsed.section : [],
                    class: Array.isArray(parsed.class) ? parsed.class : [],
                    faculty: Array.isArray(parsed.faculty) ? parsed.faculty : [],
                    room: Array.isArray(parsed.room) ? parsed.room : []
                };
            }
        } catch (_error) {
            exportOptions = { section: [], class: [], faculty: [], room: [] };
        }
    }

    function setExportTargetHint(message) {
        if (!exportTargetHint) {
            return;
        }
        exportTargetHint.textContent = message;
    }

    function fillExportTargets() {
        if (!exportViewKind || !exportSelectionMode || !exportTargets || !exportTargetWrap) {
            return;
        }

        var kind = exportViewKind.value || "all";
        var mode = exportSelectionMode.value || "all";
        var needsTargets = kind !== "all" && mode !== "all";

        exportTargets.innerHTML = "";

        if (!needsTargets) {
            exportTargetWrap.classList.add("d-none");
            setExportTargetHint("In All mode, the full selected category will be exported.");
            return;
        }

        exportTargetWrap.classList.remove("d-none");
        var options = exportOptions[kind] || [];

        options.forEach(function (entry) {
            if (!entry || typeof entry !== "object") {
                return;
            }
            var value = String(entry.value || "").trim();
            if (!value) {
                return;
            }
            var optionNode = document.createElement("option");
            optionNode.value = value;
            optionNode.textContent = String(entry.label || value);
            exportTargets.appendChild(optionNode);
        });

        if (mode === "single" && exportTargets.options.length > 0) {
            exportTargets.options[0].selected = true;
            exportTargets.size = Math.min(6, Math.max(2, exportTargets.options.length));
            setExportTargetHint("Single mode: choose exactly one target.");
        } else {
            exportTargets.size = Math.min(8, Math.max(4, exportTargets.options.length));
            setExportTargetHint("Multiple mode: choose one or more targets.");
        }
    }

    function getSelectedExportTargetValues() {
        if (!exportTargets) {
            return [];
        }
        var values = [];
        Array.prototype.forEach.call(exportTargets.options, function (optionNode) {
            if (optionNode.selected) {
                values.push(optionNode.value);
            }
        });
        return values;
    }

    function enforceSingleExportSelection() {
        if (!exportSelectionMode || !exportTargets || exportSelectionMode.value !== "single") {
            return;
        }

        var selected = getSelectedExportTargetValues();
        if (selected.length <= 1) {
            return;
        }

        var lastSelectedValue = selected[selected.length - 1];
        Array.prototype.forEach.call(exportTargets.options, function (optionNode) {
            optionNode.selected = optionNode.value === lastSelectedValue;
        });
    }

    function readOptionLabel(selectElement, value) {
        if (!selectElement || !selectElement.options) {
            return "";
        }

        for (var index = 0; index < selectElement.options.length; index += 1) {
            var option = selectElement.options[index];
            if (String(option.value) === String(value)) {
                return option.text || "";
            }
        }
        return "";
    }

    safeParseExportOptions();

    if (exportViewKind) {
        exportViewKind.addEventListener("change", function () {
            fillExportTargets();
        });
    }

    if (exportSelectionMode) {
        exportSelectionMode.addEventListener("change", function () {
            fillExportTargets();
        });
    }

    if (exportTargets) {
        exportTargets.addEventListener("change", function () {
            enforceSingleExportSelection();
        });
    }

    if (exportForm) {
        exportForm.addEventListener("submit", function (event) {
            if (!exportViewKind || !exportSelectionMode || !exportFormat) {
                return;
            }

            var kind = exportViewKind.value || "all";
            var mode = exportSelectionMode.value || "all";
            var format = exportFormat.value || "pdf";
            var selectedTargets = getSelectedExportTargetValues();

            if (kind !== "all" && mode !== "all" && selectedTargets.length === 0) {
                event.preventDefault();
                setExportTargetHint("Select at least one target before downloading.");
                return;
            }

            if (mode === "single" && selectedTargets.length !== 1) {
                event.preventDefault();
                setExportTargetHint("Single mode requires exactly one selected target.");
                return;
            }

            if (format === "jpg") {
                var isSingleCard = mode === "single" && kind !== "all" && selectedTargets.length === 1;
                if (!isSingleCard) {
                    event.preventDefault();
                    setExportTargetHint("JPG export is only available for one selected timetable card.");
                }
            }
        });
    }

    fillExportTargets();

    function setManualEditSelectionSummary(message) {
        if (!manualEditSelectionSummary) {
            return;
        }
        manualEditSelectionSummary.textContent = message;
    }

    function setManualEditLiveWarning(message, isConflict) {
        if (!manualEditLiveWarning) {
            return;
        }

        if (!message) {
            manualEditLiveWarning.classList.add("d-none");
            manualEditLiveWarning.classList.remove("is-conflict", "is-ok");
            manualEditLiveWarning.textContent = "";
            return;
        }

        manualEditLiveWarning.classList.remove("d-none");
        manualEditLiveWarning.classList.toggle("is-conflict", !!isConflict);
        manualEditLiveWarning.classList.toggle("is-ok", !isConflict);
        manualEditLiveWarning.textContent = message;
    }

    function clearMoveSourceFields() {
        if (manualEditSourceSectionHidden) {
            manualEditSourceSectionHidden.value = "";
        }
        if (manualEditSourceDayHidden) {
            manualEditSourceDayHidden.value = "";
        }
        if (manualEditSourcePeriodHidden) {
            manualEditSourcePeriodHidden.value = "";
        }
    }

    function setMoveSourceFields(slotData) {
        if (!slotData) {
            clearMoveSourceFields();
            return;
        }
        if (manualEditSourceSectionHidden) {
            manualEditSourceSectionHidden.value = slotData.sectionKey;
        }
        if (manualEditSourceDayHidden) {
            manualEditSourceDayHidden.value = slotData.dayValue;
        }
        if (manualEditSourcePeriodHidden) {
            manualEditSourcePeriodHidden.value = slotData.periodValue;
        }
    }

    function setManualEditCellHighlight(cell) {
        if (selectedManualEditCell) {
            selectedManualEditCell.classList.remove("manual-slot-selected");
        }

        selectedManualEditCell = cell;
        if (selectedManualEditCell) {
            selectedManualEditCell.classList.add("manual-slot-selected");
        }
    }

    function getManualEditSlotData(cell) {
        if (!cell) {
            return null;
        }

        var sectionKey = cell.getAttribute("data-section-key") || "";
        var dayValue = cell.getAttribute("data-day-index") || "";
        var periodValue = cell.getAttribute("data-period-index") || "";

        if (!sectionKey || !dayValue || !periodValue) {
            return null;
        }

        return {
            sectionKey: sectionKey,
            dayValue: dayValue,
            periodValue: periodValue,
            isLab: cell.getAttribute("data-is-lab") === "1",
            isLocked: cell.getAttribute("data-is-locked") === "1",
            isEmpty: cell.getAttribute("data-is-empty") === "1",
            subjectValue: cell.getAttribute("data-subject") || "",
            teacherValue: cell.getAttribute("data-teacher") || "",
            roomValue: cell.getAttribute("data-room") || ""
        };
    }

    function prefillManualEditFromCell(cell) {
        var slotData = getManualEditSlotData(cell);

        if (!slotData) {
            return null;
        }

        if (manualEditSource) {
            manualEditSource.value = "section";
            syncManualEditSource();
        }

        if (manualEditSection) {
            manualEditSection.value = slotData.sectionKey;
        }

        if (manualEditDay) {
            manualEditDay.value = slotData.dayValue;
        }

        if (manualEditPeriod) {
            manualEditPeriod.value = slotData.periodValue;
        }

        if (manualEditSubject && (!slotData.isEmpty || !manualEditSubject.value.trim())) {
            manualEditSubject.value = slotData.subjectValue;
        }

        if (manualEditTeacher && (!slotData.isEmpty || !manualEditTeacher.value.trim())) {
            manualEditTeacher.value = slotData.teacherValue;
        }

        if (manualEditRoom && (!slotData.isEmpty || !manualEditRoom.value.trim())) {
            manualEditRoom.value = slotData.roomValue;
        }

        if (manualEditAction) {
            if (slotData.isLab) {
                manualEditAction.value = "lab_double";
            } else if (slotData.isLocked) {
                manualEditAction.value = "unlock_slot";
            } else if (!slotData.isEmpty || manualEditAction.value === "clear") {
                manualEditAction.value = "theory";
            }
            syncManualEditAction();
        }

        clearMoveSourceFields();

        var dayLabel = readOptionLabel(manualEditDay, slotData.dayValue) || ("Day " + slotData.dayValue);
        var periodLabel = readOptionLabel(manualEditPeriod, slotData.periodValue) || ("Period " + slotData.periodValue);

        if (slotData.isEmpty) {
            setManualEditSelectionSummary(
                "Selected slot: "
                + slotData.sectionKey
                + " | "
                + dayLabel
                + " | "
                + periodLabel
                + " (currently free)"
            );
        } else {
            setManualEditSelectionSummary(
                "Selected slot: "
                + slotData.sectionKey
                + " | "
                + dayLabel
                + " | "
                + periodLabel
                + " ("
                + slotData.subjectValue
                + " / "
                + slotData.teacherValue
                + " / "
                + slotData.roomValue
                + (slotData.isLocked ? " | LOCKED" : "")
                + ")"
            );
        }

        selectedManualSlotData = slotData;
        return slotData;
    }

    function hideManualSlotActionBar() {
        if (!manualSlotActionBar) {
            return;
        }
        manualSlotActionBar.classList.add("d-none");
    }

    function positionManualSlotActionBar(cell) {
        if (!manualSlotActionBar || !cell) {
            return;
        }

        manualSlotActionBar.classList.remove("d-none");
        manualSlotActionBar.style.visibility = "hidden";

        var cellRect = cell.getBoundingClientRect();
        var barRect = manualSlotActionBar.getBoundingClientRect();
        var spacing = 10;
        var viewportPadding = 8;

        var top = cellRect.top - barRect.height - spacing;
        if (top < viewportPadding) {
            top = cellRect.bottom + spacing;
        }

        var left = cellRect.left + (cellRect.width / 2) - (barRect.width / 2);
        var maxLeft = window.innerWidth - barRect.width - viewportPadding;
        if (left < viewportPadding) {
            left = viewportPadding;
        }
        if (left > maxLeft) {
            left = maxLeft;
        }

        manualSlotActionBar.style.top = Math.round(top) + "px";
        manualSlotActionBar.style.left = Math.round(left) + "px";
        manualSlotActionBar.style.visibility = "visible";
    }

    function showManualSlotActionBar(cell, slotData) {
        if (!manualSlotActionBar || !slotData) {
            return;
        }

        var dayLabel = readOptionLabel(manualEditDay, slotData.dayValue) || ("Day " + slotData.dayValue);
        var periodLabel = readOptionLabel(manualEditPeriod, slotData.periodValue) || ("Period " + slotData.periodValue);

        if (manualSlotActionTitle) {
            manualSlotActionTitle.textContent = slotData.sectionKey + " | " + dayLabel + " | " + periodLabel;
        }

        if (manualSlotActionClear) {
            manualSlotActionClear.disabled = slotData.isEmpty;
        }

        if (manualSlotActionLock) {
            manualSlotActionLock.disabled = slotData.isEmpty || slotData.isLocked;
        }

        if (manualSlotActionUnlock) {
            manualSlotActionUnlock.disabled = slotData.isEmpty || !slotData.isLocked;
        }

        positionManualSlotActionBar(cell);
    }

    function submitManualEditForm() {
        if (!manualEditForm) {
            return;
        }

        if (typeof manualEditForm.requestSubmit === "function") {
            manualEditForm.requestSubmit();
            return;
        }

        manualEditForm.submit();
    }

    function applyQuickSlotAction(actionName) {
        if (!selectedManualEditCell || !manualEditAction) {
            return;
        }

        var slotData = prefillManualEditFromCell(selectedManualEditCell);
        if (!slotData) {
            return;
        }

        manualEditAction.value = actionName;
        syncManualEditAction();
        clearMoveSourceFields();

        if (
            slotData.isLocked
            && actionName !== "unlock_slot"
            && actionName !== "lock_slot"
        ) {
            setManualEditLiveWarning("This slot is locked. Use Unlock first, then apply other edits.", true);
            setManualEditSelectionSummary("Edit blocked: selected slot is locked.");
            return;
        }

        if (actionName === "clear") {
            setManualEditSelectionSummary("Applying quick clear for selected slot...");
            submitManualEditForm();
            return;
        }

        if (actionName === "lock_slot" || actionName === "unlock_slot") {
            setManualEditSelectionSummary(
                "Applying quick " + (actionName === "lock_slot" ? "lock" : "unlock") + " for selected slot..."
            );
            submitManualEditForm();
            return;
        }

        var subjectValue = manualEditSubject ? manualEditSubject.value.trim() : "";
        var teacherValue = manualEditTeacher ? manualEditTeacher.value.trim() : "";
        var roomValue = manualEditRoom ? manualEditRoom.value.trim() : "";

        if (!subjectValue || !teacherValue || !roomValue) {
            setManualEditSelectionSummary(
                "Quick "
                + (actionName === "lab_double" ? "LAB" : "theory")
                + " needs subject, faculty, and room. Fill missing values, then click Apply Edit."
            );

            if (!subjectValue && manualEditSubject) {
                manualEditSubject.focus();
            } else if (!teacherValue && manualEditTeacher) {
                manualEditTeacher.focus();
            } else if (!roomValue && manualEditRoom) {
                manualEditRoom.focus();
            }
            return;
        }

        setManualEditSelectionSummary(
            "Applying quick "
            + (actionName === "lab_double" ? "LAB" : "theory")
            + " update for selected slot..."
        );
        submitManualEditForm();
    }

    function slotIndexKey(dayValue, periodValue) {
        return String(dayValue) + "::" + String(periodValue);
    }

    function buildSlotIndex() {
        var index = {};
        manualEditSlotCells.forEach(function (cell) {
            var slotData = getManualEditSlotData(cell);
            if (!slotData) {
                return;
            }
            var key = slotIndexKey(slotData.dayValue, slotData.periodValue);
            if (!index[key]) {
                index[key] = [];
            }
            index[key].push({
                cell: cell,
                slotData: slotData
            });
        });
        return index;
    }

    function evaluateDropCandidate(sourceSlotData, targetSlotData, slotIndex) {
        if (!sourceSlotData || !targetSlotData) {
            return {
                ok: false,
                message: "Invalid drag target."
            };
        }

        if (sourceSlotData.isEmpty) {
            return {
                ok: false,
                message: "Only occupied slots can be dragged."
            };
        }

        if (sourceSlotData.isLocked) {
            return {
                ok: false,
                message: "Locked slots cannot be moved until unlocked."
            };
        }

        if (
            sourceSlotData.sectionKey === targetSlotData.sectionKey
            && sourceSlotData.dayValue === targetSlotData.dayValue
            && sourceSlotData.periodValue === targetSlotData.periodValue
        ) {
            return {
                ok: false,
                message: "Source and target slots are the same."
            };
        }

        if (!targetSlotData.isEmpty) {
            return {
                ok: false,
                message: "Target slot is occupied. Pick a free slot to move."
            };
        }

        if (targetSlotData.isLocked) {
            return {
                ok: false,
                message: "Target slot is locked. Unlock it before moving here."
            };
        }

        var targetDay = targetSlotData.dayValue;
        var targetPeriod = targetSlotData.periodValue;
        var slotEntries = slotIndex[slotIndexKey(targetDay, targetPeriod)] || [];

        var teacherConflict = false;
        var roomConflict = false;

        slotEntries.forEach(function (entry) {
            var other = entry.slotData;
            var sameSource = (
                other.sectionKey === sourceSlotData.sectionKey
                && other.dayValue === sourceSlotData.dayValue
                && other.periodValue === sourceSlotData.periodValue
            );
            if (sameSource) {
                return;
            }

            if (
                sourceSlotData.teacherValue
                && other.teacherValue
                && sourceSlotData.teacherValue === other.teacherValue
            ) {
                teacherConflict = true;
            }

            if (
                sourceSlotData.roomValue
                && other.roomValue
                && sourceSlotData.roomValue === other.roomValue
            ) {
                roomConflict = true;
            }
        });

        if (teacherConflict && roomConflict) {
            return {
                ok: false,
                message: "Clash warning: same faculty and room are already used in this slot."
            };
        }

        if (teacherConflict) {
            return {
                ok: false,
                message: "Clash warning: faculty is already scheduled in this slot."
            };
        }

        if (roomConflict) {
            return {
                ok: false,
                message: "Clash warning: room is already allocated in this slot."
            };
        }

        return {
            ok: true,
            message: "Move preview looks valid. Drop to apply edit."
        };
    }

    function clearDropHints() {
        manualEditSlotCells.forEach(function (cell) {
            cell.classList.remove("manual-slot-drop-target", "manual-slot-drop-conflict");
        });
    }

    function handleMoveDrop(targetCell) {
        if (!targetCell || !draggingManualSlotData || !manualEditAction) {
            return;
        }

        var targetSlotData = getManualEditSlotData(targetCell);
        var slotIndex = buildSlotIndex();
        var preview = evaluateDropCandidate(draggingManualSlotData, targetSlotData, slotIndex);

        if (!preview.ok) {
            setManualEditLiveWarning(preview.message, true);
            setManualEditSelectionSummary("Move cancelled: " + preview.message);
            return;
        }

        if (manualEditSource) {
            manualEditSource.value = "section";
            syncManualEditSource();
        }

        if (manualEditSection) {
            manualEditSection.value = targetSlotData.sectionKey;
        }
        if (manualEditDay) {
            manualEditDay.value = targetSlotData.dayValue;
        }
        if (manualEditPeriod) {
            manualEditPeriod.value = targetSlotData.periodValue;
        }

        if (manualEditSubject) {
            manualEditSubject.value = draggingManualSlotData.subjectValue;
        }
        if (manualEditTeacher) {
            manualEditTeacher.value = draggingManualSlotData.teacherValue;
        }
        if (manualEditRoom) {
            manualEditRoom.value = draggingManualSlotData.roomValue;
        }

        setMoveSourceFields(draggingManualSlotData);
        manualEditAction.value = "move";
        syncManualEditAction();

        var sourceDayLabel = readOptionLabel(manualEditDay, draggingManualSlotData.dayValue) || ("Day " + draggingManualSlotData.dayValue);
        var sourcePeriodLabel = readOptionLabel(manualEditPeriod, draggingManualSlotData.periodValue) || ("Period " + draggingManualSlotData.periodValue);
        var targetDayLabel = readOptionLabel(manualEditDay, targetSlotData.dayValue) || ("Day " + targetSlotData.dayValue);
        var targetPeriodLabel = readOptionLabel(manualEditPeriod, targetSlotData.periodValue) || ("Period " + targetSlotData.periodValue);

        setManualEditSelectionSummary(
            "Moving "
            + draggingManualSlotData.subjectValue
            + " ("
            + draggingManualSlotData.sectionKey
            + ") from "
            + sourceDayLabel
            + " "
            + sourcePeriodLabel
            + " to "
            + targetSlotData.sectionKey
            + " | "
            + targetDayLabel
            + " "
            + targetPeriodLabel
            + "..."
        );
        setManualEditLiveWarning("Move submitted. Server is validating clashes and synchronizing all views.", false);
        submitManualEditForm();
    }

    if (searchInput && kindSelect && clearButton && counter && emptyMessage && cards.length > 0) {
        function applyFilters() {
            var searchValue = normalize(searchInput.value);
            var selectedKind = kindSelect.value;
            var visibleCount = 0;

            cards.forEach(function (card) {
                var cardKind = card.getAttribute("data-result-kind") || "";
                var cardSearch = normalize(card.getAttribute("data-result-search"));
                var kindMatches = selectedKind === "all" || cardKind === selectedKind;
                var searchMatches = !searchValue || cardSearch.indexOf(searchValue) >= 0;
                var shouldShow = kindMatches && searchMatches;

                card.classList.toggle("d-none", !shouldShow);
                if (shouldShow) {
                    visibleCount += 1;
                }
            });

            if (!searchValue && selectedKind === "all") {
                counter.textContent = "Showing all timetable cards";
            } else {
                counter.textContent = "Visible timetable cards: " + visibleCount;
            }

            emptyMessage.classList.toggle("d-none", visibleCount !== 0);
        }

        searchInput.addEventListener("input", applyFilters);
        kindSelect.addEventListener("change", applyFilters);
        clearButton.addEventListener("click", function () {
            searchInput.value = "";
            kindSelect.value = "all";
            applyFilters();
            searchInput.focus();
        });

        applyFilters();
    }

    if (manualEditSource && manualEditSectionWrap && manualEditFacultyWrap) {
        syncManualEditSource = function () {
            var facultyMode = manualEditSource.value === "faculty";
            manualEditSectionWrap.classList.toggle("d-none", facultyMode);
            manualEditFacultyWrap.classList.toggle("d-none", !facultyMode);
            if (manualEditFaculty) {
                manualEditFaculty.required = facultyMode;
            }
        };

        manualEditSource.addEventListener("change", syncManualEditSource);
        syncManualEditSource();
    }

    if (manualEditAction && manualEditDetailFields) {
        syncManualEditAction = function () {
            var clearMode = manualEditAction.value === "clear";
            var moveMode = manualEditAction.value === "move";
            var lockMode = manualEditAction.value === "lock_slot" || manualEditAction.value === "unlock_slot";
            var hideDetails = clearMode || moveMode || lockMode;
            manualEditDetailFields.classList.toggle("d-none", hideDetails);

            if (manualEditSubject) {
                manualEditSubject.required = !hideDetails;
            }
            if (manualEditTeacher) {
                manualEditTeacher.required = !hideDetails;
            }
            if (manualEditRoom) {
                manualEditRoom.required = !hideDetails;
            }
        };

        manualEditAction.addEventListener("change", syncManualEditAction);
        syncManualEditAction();
    }

    if (manualEditSetClear && manualEditAction) {
        manualEditSetClear.addEventListener("click", function () {
            manualEditAction.value = "clear";
            syncManualEditAction();
            clearMoveSourceFields();
            setManualEditLiveWarning("", false);
            setManualEditSelectionSummary("Action set to Clear Slot. Click Apply Edit to submit.");
            manualEditSetClear.blur();
        });
    }

    if (manualEditForm && manualEditSlotCells.length > 0) {
        manualEditSlotCells.forEach(function (cell) {
            cell.addEventListener("click", function () {
                var slotData = prefillManualEditFromCell(cell);
                if (!slotData) {
                    return;
                }

                setManualEditCellHighlight(cell);
                showManualSlotActionBar(cell, slotData);
                setManualEditLiveWarning("", false);
            });

            var cellSlotData = getManualEditSlotData(cell);
            if (cellSlotData && !cellSlotData.isEmpty && !cellSlotData.isLocked) {
                cell.setAttribute("draggable", "true");
            }

            cell.addEventListener("dragstart", function (event) {
                var slotData = getManualEditSlotData(cell);
                if (!slotData || slotData.isEmpty || slotData.isLocked) {
                    event.preventDefault();
                    setManualEditLiveWarning("Locked slots cannot be dragged. Unlock first to move.", true);
                    return;
                }

                draggingManualSlotCell = cell;
                draggingManualSlotData = slotData;
                cell.classList.add("manual-slot-dragging");
                if (event.dataTransfer) {
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", JSON.stringify(slotData));
                }

                setManualEditLiveWarning(
                    "Dragging "
                    + slotData.subjectValue
                    + " ("
                    + slotData.sectionKey
                    + "). Drop on a free target slot.",
                    false
                );
            });

            cell.addEventListener("dragend", function () {
                if (draggingManualSlotCell) {
                    draggingManualSlotCell.classList.remove("manual-slot-dragging");
                }
                draggingManualSlotCell = null;
                draggingManualSlotData = null;
                clearDropHints();
            });

            cell.addEventListener("dragover", function (event) {
                if (!draggingManualSlotData) {
                    return;
                }
                event.preventDefault();

                var targetSlotData = getManualEditSlotData(cell);
                var slotIndex = buildSlotIndex();
                var preview = evaluateDropCandidate(draggingManualSlotData, targetSlotData, slotIndex);

                clearDropHints();
                cell.classList.add(preview.ok ? "manual-slot-drop-target" : "manual-slot-drop-conflict");
                setManualEditLiveWarning(preview.message, !preview.ok);

                if (event.dataTransfer) {
                    event.dataTransfer.dropEffect = preview.ok ? "move" : "none";
                }
            });

            cell.addEventListener("dragleave", function () {
                cell.classList.remove("manual-slot-drop-target", "manual-slot-drop-conflict");
            });

            cell.addEventListener("drop", function (event) {
                event.preventDefault();
                clearDropHints();
                handleMoveDrop(cell);
            });
        });

        manualEditForm.addEventListener("submit", function () {
            hideManualSlotActionBar();
            clearDropHints();
        });

        if (manualSlotActionClear) {
            manualSlotActionClear.addEventListener("click", function () {
                applyQuickSlotAction("clear");
            });
        }

        if (manualSlotActionTheory) {
            manualSlotActionTheory.addEventListener("click", function () {
                applyQuickSlotAction("theory");
            });
        }

        if (manualSlotActionLab) {
            manualSlotActionLab.addEventListener("click", function () {
                applyQuickSlotAction("lab_double");
            });
        }

        if (manualSlotActionLock) {
            manualSlotActionLock.addEventListener("click", function () {
                applyQuickSlotAction("lock_slot");
            });
        }

        if (manualSlotActionUnlock) {
            manualSlotActionUnlock.addEventListener("click", function () {
                applyQuickSlotAction("unlock_slot");
            });
        }

        if (manualSlotActionClose) {
            manualSlotActionClose.addEventListener("click", function () {
                hideManualSlotActionBar();
                setManualEditCellHighlight(null);
            });
        }

        document.addEventListener("click", function (event) {
            if (!manualSlotActionBar || manualSlotActionBar.classList.contains("d-none")) {
                return;
            }

            var target = event.target;
            var insideBar = manualSlotActionBar.contains(target);
            var onEditableCell = target && target.closest
                ? target.closest(".manual-slot-cell[data-slot-editable='1']")
                : null;

            if (!insideBar && !onEditableCell) {
                hideManualSlotActionBar();
                setManualEditCellHighlight(null);
                setManualEditLiveWarning("", false);
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                hideManualSlotActionBar();
                setManualEditCellHighlight(null);
                clearDropHints();
                setManualEditLiveWarning("", false);
            }
        });

        var repositionQuickBar = function () {
            if (
                selectedManualEditCell
                && manualSlotActionBar
                && !manualSlotActionBar.classList.contains("d-none")
            ) {
                positionManualSlotActionBar(selectedManualEditCell);
            }
        };

        window.addEventListener("resize", repositionQuickBar);
        document.addEventListener("scroll", function () {
            repositionQuickBar();
        }, true);
    } else {
        if (manualSlotActionBar) {
            hideManualSlotActionBar();
        }
    }

    if (manualEditSource && manualEditSource.value === "faculty" && manualEditSelectionSummary) {
        setManualEditSelectionSummary(
            "Faculty mode selected. Pick faculty/day/period or click a timetable cell to switch to section slot edit."
        );
    }
});