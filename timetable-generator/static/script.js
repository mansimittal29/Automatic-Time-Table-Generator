function splitNonEmptyLines(rawValue) {
    return rawValue
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
}

function countNonEmptyLines(rawValue) {
    return splitNonEmptyLines(rawValue).length;
}

function getElementValue(id) {
    var field = document.getElementById(id);
    return field ? field.value : "";
}

function parseLunchPeriods(rawValue) {
    if (!rawValue.trim()) {
        return [];
    }

    return rawValue
        .replace(/;/g, ",")
        .split(",")
        .map((token) => token.trim())
        .filter((token) => token.length > 0)
        .map((token) => parseInt(token, 10));
}

function parseLunchConfiguration(rawValue, workingDays, periodsPerDay) {
    var normalizedDays = Number.isNaN(workingDays) || workingDays < 1 ? 1 : workingDays;
    var normalizedPeriods = Number.isNaN(periodsPerDay) || periodsPerDay < 1 ? 1 : periodsPerDay;
    var lunchTokens = parseLunchPeriods(rawValue);
    var errors = [];
    var parsedNumbers = [];

    lunchTokens.forEach(function (token) {
        if (Number.isNaN(token) || token < 1 || token > normalizedPeriods) {
            errors.push("Lunch period values must be between 1 and " + normalizedPeriods + ".");
            return;
        }
        parsedNumbers.push(token);
    });

    var byDay = [];
    for (var dayIndex = 0; dayIndex < normalizedDays; dayIndex += 1) {
        byDay.push(new Set());
    }

    if (errors.length === 0 && parsedNumbers.length > 0) {
        if (parsedNumbers.length === normalizedDays) {
            parsedNumbers.forEach(function (periodNumber, dayIndex) {
                byDay[dayIndex].add(periodNumber);
            });
        } else {
            var sharedSet = new Set(parsedNumbers);
            byDay = byDay.map(function () {
                return new Set(sharedSet);
            });
        }
    }

    var teachablePerDayMin = normalizedPeriods;
    var totalTeachableSlots = 0;

    byDay.forEach(function (daySet) {
        var teachableToday = Math.max(0, normalizedPeriods - daySet.size);
        teachablePerDayMin = Math.min(teachablePerDayMin, teachableToday);
        totalTeachableSlots += teachableToday;
    });

    if (!byDay.length) {
        teachablePerDayMin = normalizedPeriods;
    }

    return {
        errors: errors,
        byDay: byDay,
        teachablePerDayMin: teachablePerDayMin,
        totalTeachableSlots: totalTeachableSlots,
    };
}

function getAssignmentSource() {
    var selected = document.querySelector("input[name='assignment_source']:checked");
    return selected ? selected.value : "manual";
}

function toggleAssignmentSourceUI() {
    var assignmentsField = document.getElementById("assignments");
    var copySampleButton = document.getElementById("copy-sample-block");
    var sourceHint = document.getElementById("assignment-source-hint");
    var assignmentSource = getAssignmentSource();
    var isMaster = assignmentSource === "master";

    if (assignmentsField) {
        assignmentsField.required = !isMaster;
        assignmentsField.readOnly = isMaster;
        assignmentsField.classList.toggle("bg-light", isMaster);
    }

    if (copySampleButton) {
        copySampleButton.disabled = isMaster;
    }

    if (sourceHint) {
        sourceHint.textContent = isMaster
            ? "Master mode uses rows from Assignment Master. Textarea is preview-only."
            : "Format: Class,Standard,Section,Subject,Teacher,Lectures[,Type[,AllowedRooms[,DailyMax]]]";
    }
}

function parseDayToken(dayRaw, workingDays) {
    var normalized = String(dayRaw || "").trim().toLowerCase();
    if (!normalized) {
        return { valid: false, message: "Day value is required." };
    }

    if (/^\d+$/.test(normalized)) {
        var dayNumber = parseInt(normalized, 10);
        if (dayNumber < 1 || dayNumber > workingDays) {
            return { valid: false, message: "Day must be between 1 and " + workingDays + "." };
        }
        return { valid: true, dayIndex: dayNumber - 1 };
    }

    var dayMap = {
        monday: 0,
        mon: 0,
        tuesday: 1,
        tue: 1,
        wednesday: 2,
        wed: 2,
        thursday: 3,
        thu: 3,
        friday: 4,
        fri: 4,
        saturday: 5,
        sat: 5,
        sunday: 6,
        sun: 6,
    };

    if (!(normalized in dayMap)) {
        return { valid: false, message: "Day must be a number or valid day name." };
    }

    if (dayMap[normalized] >= workingDays) {
        return {
            valid: false,
            message: "Day name exceeds configured working days (" + workingDays + ").",
        };
    }

    return { valid: true, dayIndex: dayMap[normalized] };
}

function parseFacultyUnavailabilityLines(rawValue, workingDays, periodsPerDay) {
    var lines = splitNonEmptyLines(rawValue);
    var errors = [];

    lines.forEach(function (line, index) {
        var parts = line.split(",").map(function (value) {
            return value.trim();
        });

        if (parts.length !== 3) {
            errors.push("Faculty unavailability line " + (index + 1) + " must have 3 values.");
            return;
        }

        if (!parts[0]) {
            errors.push("Faculty unavailability line " + (index + 1) + " has empty faculty name.");
            return;
        }

        var dayResult = parseDayToken(parts[1], workingDays);
        if (!dayResult.valid) {
            errors.push("Faculty unavailability line " + (index + 1) + ": " + dayResult.message);
            return;
        }

        var periodNumber = parseInt(parts[2], 10);
        if (Number.isNaN(periodNumber) || periodNumber < 1 || periodNumber > periodsPerDay) {
            errors.push(
                "Faculty unavailability line " + (index + 1) + " period must be between 1 and " + periodsPerDay + "."
            );
        }
    });

    return {
        rowCount: lines.length,
        errors: errors,
    };
}

function parseFixedSlots(rawValue, workingDays, periodsPerDay, lunchPeriods, roomSet) {
    var lines = splitNonEmptyLines(rawValue);
    var errors = [];

    lines.forEach(function (line, index) {
        var parts = line.split(",").map(function (value) {
            return value.trim();
        });

        if (parts.length < 7 || parts.length > 9) {
            errors.push("Fixed slot line " + (index + 1) + " must have 7 to 9 values.");
            return;
        }

        for (var requiredIndex = 0; requiredIndex < 7; requiredIndex += 1) {
            if (!parts[requiredIndex]) {
                errors.push("Fixed slot line " + (index + 1) + " has empty required values.");
                return;
            }
        }

        var dayResult = parseDayToken(parts[5], workingDays);
        if (!dayResult.valid) {
            errors.push("Fixed slot line " + (index + 1) + ": " + dayResult.message);
            return;
        }

        var startPeriod = parseInt(parts[6], 10);
        if (Number.isNaN(startPeriod) || startPeriod < 1 || startPeriod > periodsPerDay) {
            errors.push("Fixed slot line " + (index + 1) + " start period must be between 1 and " + periodsPerDay + ".");
            return;
        }

        var duration = 1;
        var roomName = "";
        if (parts.length === 8) {
            if (/^\d+$/.test(parts[7])) {
                duration = parseInt(parts[7], 10);
            } else {
                roomName = parts[7];
            }
        }
        if (parts.length === 9) {
            duration = parseInt(parts[7], 10);
            roomName = parts[8];
        }

        if (Number.isNaN(duration) || duration < 1 || duration > periodsPerDay) {
            errors.push("Fixed slot line " + (index + 1) + " has invalid duration.");
            return;
        }

        var endPeriod = startPeriod + duration - 1;
        if (endPeriod > periodsPerDay) {
            errors.push("Fixed slot line " + (index + 1) + " duration exceeds periods per day.");
            return;
        }

        for (var period = startPeriod; period <= endPeriod; period += 1) {
            if (lunchPeriods.has(period)) {
                errors.push("Fixed slot line " + (index + 1) + " intersects lunch break period " + period + ".");
                return;
            }
        }

        if (roomName && roomSet && roomSet.size > 0 && !roomSet.has(roomName)) {
            errors.push("Fixed slot line " + (index + 1) + " references room not present in Rooms list.");
        }
    });

    return {
        rowCount: lines.length,
        errors: errors,
    };
}

function parseSectionGroup(sectionRaw) {
    var cleaned = String(sectionRaw || "").trim();
    var upperCleaned = cleaned.toUpperCase();
    var markerIndex = upperCleaned.lastIndexOf("-G");
    if (markerIndex <= 0) {
        return { baseSection: cleaned, groupNumber: null };
    }

    var suffix = upperCleaned.slice(markerIndex + 2);
    if (suffix === "1" || suffix === "2" || suffix === "3") {
        return {
            baseSection: cleaned.slice(0, markerIndex).trim(),
            groupNumber: parseInt(suffix, 10),
        };
    }

    return { baseSection: cleaned, groupNumber: null };
}

function parseAllowedRooms(rawValue) {
    return String(rawValue || "")
        .replace(/;/g, "|")
        .split("|")
        .map(function (value) {
            return value.trim();
        })
        .filter(function (value) {
            return value.length > 0;
        });
}

function parseAssignmentLines(rawValue) {
    var lines = splitNonEmptyLines(rawValue);
    var errors = [];
    var totalLectures = 0;
    var sectionKeys = new Set();
    var teacherNames = new Set();
    var labRows = 0;
    var dailyMaxRows = 0;
    var labStatsBySection = {};

    lines.forEach(function (line, index) {
        var parts = line.split(",").map(function (value) {
            return value.trim();
        });

        if (parts.length < 6 || parts.length > 9) {
            errors.push("Line " + (index + 1) + " must have 6-9 comma-separated values.");
            return;
        }

        var className = parts[0];
        var standard = parts[1];
        var section = parts[2];
        var subject = parts[3];
        var teacher = parts[4];
        var lecturesRaw = parts[5];
        var sectionGroup = parseSectionGroup(section);
        var typeRaw = parts.length >= 7 ? parts[6].toUpperCase() : "THEORY";
        var allowedRoomsRaw = parts.length >= 8 ? parts[7] : "";
        var dailyMaxRaw = parts.length === 9 ? parts[8] : "";

        if (!className || !standard || !section || !subject || !teacher || !lecturesRaw) {
            errors.push("Line " + (index + 1) + " has empty required values.");
            return;
        }

        var lectures = parseInt(lecturesRaw, 10);
        if (Number.isNaN(lectures) || lectures <= 0) {
            errors.push("Line " + (index + 1) + " has invalid lectures value.");
            return;
        }

        var isLab = ["LAB", "PRACTICAL", "P", "LABORATORY"].indexOf(typeRaw) >= 0;
        if (isLab) {
            labRows += 1;
            var allowedRooms = parseAllowedRooms(allowedRoomsRaw);
            if (!allowedRooms.length) {
                errors.push("Line " + (index + 1) + " is LAB but has no allowed rooms.");
                return;
            }

            if (sectionGroup.groupNumber !== null) {
                errors.push(
                    "Line "
                    + (index + 1)
                    + " uses grouped section "
                    + section
                    + " for LAB. Enter LAB rows on base section only (for example A), and generator will auto-split G1/G2/G3."
                );
                return;
            }

            if (lectures % 2 !== 0) {
                errors.push("Line " + (index + 1) + " is LAB and lectures must be even for double periods.");
                return;
            }

            var sectionStatsKey = className + "|" + standard + "|" + sectionGroup.baseSection;
            if (!labStatsBySection[sectionStatsKey]) {
                labStatsBySection[sectionStatsKey] = {
                    label: className + ", " + standard + ", " + sectionGroup.baseSection,
                    sessionCount: 0,
                    teachers: new Set(),
                    rooms: new Set(),
                };
            }

            var sectionStats = labStatsBySection[sectionStatsKey];
            sectionStats.sessionCount += lectures / 2;
            sectionStats.teachers.add(teacher);
            allowedRooms.forEach(function (roomName) {
                sectionStats.rooms.add(roomName);
            });
        }

        if (dailyMaxRaw) {
            var dailyMax = parseInt(dailyMaxRaw, 10);
            if (Number.isNaN(dailyMax) || dailyMax <= 0) {
                errors.push("Line " + (index + 1) + " has invalid DailyMax value.");
                return;
            }
            if (isLab && dailyMax < 2) {
                errors.push("Line " + (index + 1) + " is LAB and DailyMax must be at least 2.");
                return;
            }
            dailyMaxRows += 1;
        }

        totalLectures += lectures;
        sectionKeys.add(className + "|" + standard + "|" + section);
        teacherNames.add(teacher);
    });

    Object.keys(labStatsBySection).forEach(function (sectionStatsKey) {
        var sectionStats = labStatsBySection[sectionStatsKey];
        if (sectionStats.sessionCount % 3 !== 0) {
            errors.push(
                "LAB rows for "
                + sectionStats.label
                + " create "
                + sectionStats.sessionCount
                + " lab sessions (lectures/2). Use multiples of 3 so G1/G2/G3 can run in the same slot."
            );
        }

        if (sectionStats.teachers.size < 3) {
            errors.push(
                "LAB rows for "
                + sectionStats.label
                + " have only "
                + sectionStats.teachers.size
                + " distinct faculty. Provide at least 3 distinct faculty for synchronized G1/G2/G3 labs."
            );
        }

        if (sectionStats.rooms.size < 3) {
            errors.push(
                "LAB rows for "
                + sectionStats.label
                + " have only "
                + sectionStats.rooms.size
                + " distinct allowed rooms. Provide at least 3 rooms for distinct G1/G2/G3 allocation."
            );
        }
    });

    return {
        rowCount: lines.length,
        sectionCount: sectionKeys.size,
        teacherCount: teacherNames.size,
        totalLectures: totalLectures,
        labRows: labRows,
        dailyMaxRows: dailyMaxRows,
        errors: errors,
    };
}

function parseSectionHomeRooms(rawValue) {
    var lines = splitNonEmptyLines(rawValue);
    var errors = [];

    lines.forEach(function (line, index) {
        var parts = line.split(",").map(function (value) {
            return value.trim();
        });
        if (parts.length !== 4) {
            errors.push("Section home room line " + (index + 1) + " must have 4 values.");
            return;
        }

        if (!parts[0] || !parts[1] || !parts[2] || !parts[3]) {
            errors.push("Section home room line " + (index + 1) + " has empty values.");
        }
    });

    return {
        rowCount: lines.length,
        errors: errors,
    };
}

function parseFacultyOverrides(rawValue, maxAllowed) {
    var lines = splitNonEmptyLines(rawValue);
    var errors = [];

    lines.forEach(function (line, index) {
        var parts = line.split(",").map(function (value) {
            return value.trim();
        });
        if (parts.length !== 2) {
            errors.push("Faculty limit line " + (index + 1) + " must have 2 values.");
            return;
        }

        var teacher = parts[0];
        var maxPeriods = parseInt(parts[1], 10);
        if (!teacher || Number.isNaN(maxPeriods) || maxPeriods <= 0) {
            errors.push("Faculty limit line " + (index + 1) + " is invalid.");
            return;
        }

        if (typeof maxAllowed === "number" && maxAllowed > 0 && maxPeriods > maxAllowed) {
            errors.push(
                "Faculty limit line " + (index + 1) + " exceeds available teaching periods/day (" + maxAllowed + ")."
            );
        }
    });

    return {
        rowCount: lines.length,
        errors: errors,
    };
}

function setCounter(elementId, text) {
    var element = document.getElementById(elementId);
    if (!element) {
        return;
    }
    element.textContent = text;
}

function calculateSlotsPerSection() {
    var workingDays = parseInt(document.getElementById("working_days").value || "0", 10);
    var periodsPerDay = parseInt(document.getElementById("periods_per_day").value || "0", 10);
    var lunchConfig = parseLunchConfiguration(
        getElementValue("lunch_break_periods"),
        workingDays,
        periodsPerDay
    );

    if (Number.isNaN(workingDays) || Number.isNaN(periodsPerDay) || workingDays <= 0 || periodsPerDay <= 0) {
        return 0;
    }

    if (lunchConfig.errors.length > 0) {
        return 0;
    }

    return lunchConfig.totalTeachableSlots;
}

function calculateGlobalCapacity(slotsPerSection, sectionCount, roomCount) {
    if (slotsPerSection <= 0 || sectionCount <= 0 || roomCount <= 0) {
        return 0;
    }

    var maxParallel = Math.min(sectionCount, roomCount);
    return slotsPerSection * maxParallel;
}

function validateLunchConfiguration(lunchConfig, periodsPerDay) {
    if (lunchConfig.errors.length > 0) {
        return lunchConfig.errors[0];
    }

    for (var dayIndex = 0; dayIndex < lunchConfig.byDay.length; dayIndex += 1) {
        if (lunchConfig.byDay[dayIndex].size >= periodsPerDay) {
            return "Lunch breaks cannot occupy all periods on day " + (dayIndex + 1) + ". Keep at least one teaching period.";
        }
    }

    return "";
}

function fallbackCopyText(text) {
    var tempArea = document.createElement("textarea");
    tempArea.value = text;
    tempArea.setAttribute("readonly", "readonly");
    tempArea.style.position = "absolute";
    tempArea.style.left = "-9999px";
    document.body.appendChild(tempArea);
    tempArea.select();
    tempArea.setSelectionRange(0, tempArea.value.length);

    var copied = false;
    try {
        copied = document.execCommand("copy");
    } catch (error) {
        copied = false;
    }

    document.body.removeChild(tempArea);
    return copied;
}

function updateAll() {
    var assignmentSource = getAssignmentSource();
    var roomsText = getElementValue("rooms");
    var assignmentsText = getElementValue("assignments");
    var homeRoomsText = getElementValue("section_classrooms");
    var facultyLimitsText = getElementValue("faculty_daily_limits");
    var workingDays = parseInt(getElementValue("working_days") || "0", 10);
    var periodsPerDay = parseInt(getElementValue("periods_per_day") || "0", 10);
    var normalizedWorkingDays = workingDays > 0 ? workingDays : 7;
    var normalizedPeriodsPerDay = periodsPerDay > 0 ? periodsPerDay : 10;
    var lunchConfig = parseLunchConfiguration(
        getElementValue("lunch_break_periods"),
        normalizedWorkingDays,
        normalizedPeriodsPerDay
    );
    var masterCountRaw = document.getElementById("assignment_master_count");
    var assignmentMasterCount = masterCountRaw ? parseInt(masterCountRaw.value || "0", 10) : 0;

    var teachablePerDay = periodsPerDay > 0 ? lunchConfig.teachablePerDayMin : 0;

    var roomCount = countNonEmptyLines(roomsText);
    var parsedAssignments = parseAssignmentLines(assignmentsText);
    var parsedHomes = parseSectionHomeRooms(homeRoomsText);
    var parsedFacultyLimits = parseFacultyOverrides(
        facultyLimitsText,
        teachablePerDay > 0 ? teachablePerDay : undefined
    );
    var slotsPerSection = calculateSlotsPerSection();
    var globalCapacity = calculateGlobalCapacity(
        slotsPerSection,
        parsedAssignments.sectionCount,
        roomCount
    );

    setCounter("rooms-count", "Rooms: " + roomCount);
    setCounter(
        "assignments-count",
        assignmentSource === "master"
            ? "Assignment Rows (Master): " + assignmentMasterCount + (parsedAssignments.rowCount > 0 ? " | Preview: " + parsedAssignments.rowCount : "")
            : "Assignment Rows: " + parsedAssignments.rowCount
    );
    setCounter("sections-count", "Sections: " + parsedAssignments.sectionCount);
    setCounter("teachers-count", "Faculty: " + parsedAssignments.teacherCount);
    setCounter(
        "lecture-sum",
        "Total Lectures: "
            + parsedAssignments.totalLectures
            + " | LAB Rows: "
            + parsedAssignments.labRows
            + " | DailyMax Rows: "
            + parsedAssignments.dailyMaxRows
    );
    setCounter("home-rooms-count", "Section Home Rooms: " + parsedHomes.rowCount);
    setCounter("faculty-limits-count", "Faculty Overrides: " + parsedFacultyLimits.rowCount);
    setCounter(
        "capacity-info",
        "Estimated Global Teaching Capacity: " + globalCapacity + " lectures"
    );
}

document.addEventListener("DOMContentLoaded", function () {
    var sampleAssignmentBlock = [
        "Class-01,Year-1,A,Mathematics,Faculty-01,4,THEORY,,2",
        "Class-01,Year-1,A,Programming Fundamentals,Faculty-02,4,THEORY,,2",
        "Class-01,Year-1,A,Data Structures,Faculty-03,4,THEORY,,2",
        "Class-01,Year-1,A,Database Systems,Faculty-04,4,THEORY,,2",
        "Class-01,Year-1,A,Communication Skills,Faculty-05,4,THEORY,,2",
        "Class-01,Year-1,A,Programming Lab,Faculty-51,2,LAB,LAB-01|LAB-02|LAB-03|LAB-04|LAB-05|LAB-06|LAB-07|LAB-08,2",
        "Class-01,Year-1,A,Electronics Lab,Faculty-52,2,LAB,LAB-21|LAB-22|LAB-23|LAB-24|LAB-25|LAB-26|LAB-27|LAB-28,2",
        "Class-01,Year-1,A,Database Lab,Faculty-53,2,LAB,LAB-41|LAB-42|LAB-43|LAB-44|LAB-45|LAB-46|LAB-47|LAB-48,2",
        "Class-01,Year-1,A,Networks Lab,Faculty-54,2,LAB,LAB-09|LAB-10|LAB-11|LAB-12|LAB-13|LAB-14|LAB-15|LAB-16,2",
        "Class-01,Year-1,A,AI Lab,Faculty-55,2,LAB,LAB-29|LAB-30|LAB-31|LAB-32|LAB-33|LAB-34|LAB-35|LAB-36,2",
        "Class-01,Year-1,A,IoT Lab,Faculty-56,2,LAB,LAB-49|LAB-50|LAB-51|LAB-52|LAB-53|LAB-54|LAB-55,2",
        "Class-01,Year-1,B,Mathematics,Faculty-57,4,THEORY,,2",
        "Class-01,Year-1,B,Programming Fundamentals,Faculty-58,4,THEORY,,2",
        "Class-01,Year-1,B,Data Structures,Faculty-59,4,THEORY,,2",
        "Class-01,Year-1,B,Database Systems,Faculty-60,4,THEORY,,2",
        "Class-01,Year-1,B,Communication Skills,Faculty-61,4,THEORY,,2",
        "Class-01,Year-1,B,Programming Lab,Faculty-62,2,LAB,LAB-01|LAB-02|LAB-03|LAB-04|LAB-05|LAB-06|LAB-07|LAB-08,2",
        "Class-01,Year-1,B,Electronics Lab,Faculty-63,2,LAB,LAB-21|LAB-22|LAB-23|LAB-24|LAB-25|LAB-26|LAB-27|LAB-28,2",
        "Class-01,Year-1,B,Database Lab,Faculty-64,2,LAB,LAB-41|LAB-42|LAB-43|LAB-44|LAB-45|LAB-46|LAB-47|LAB-48,2",
        "Class-01,Year-1,B,Networks Lab,Faculty-65,2,LAB,LAB-09|LAB-10|LAB-11|LAB-12|LAB-13|LAB-14|LAB-15|LAB-16,2",
        "Class-01,Year-1,B,AI Lab,Faculty-66,2,LAB,LAB-29|LAB-30|LAB-31|LAB-32|LAB-33|LAB-34|LAB-35|LAB-36,2",
        "Class-01,Year-1,B,IoT Lab,Faculty-67,2,LAB,LAB-49|LAB-50|LAB-51|LAB-52|LAB-53|LAB-54|LAB-55,2"
    ].join("\n");

    function setCopyFeedback(message, isError) {
        var feedback = document.getElementById("copy-sample-feedback");
        if (!feedback) {
            return;
        }

        feedback.textContent = message;
        feedback.style.color = isError ? "#b02a37" : "#49698c";
    }

    var copySampleButton = document.getElementById("copy-sample-block");
    if (copySampleButton) {
        copySampleButton.addEventListener("click", function () {
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(sampleAssignmentBlock).then(function () {
                    setCopyFeedback("Sample block copied.", false);
                }).catch(function () {
                    var copiedFallback = fallbackCopyText(sampleAssignmentBlock);
                    if (copiedFallback) {
                        setCopyFeedback("Sample block copied.", false);
                    } else {
                        setCopyFeedback("Could not copy automatically. Select and copy the sample text manually.", true);
                    }
                });
                return;
            }

            var copied = fallbackCopyText(sampleAssignmentBlock);
            if (copied) {
                setCopyFeedback("Sample block copied.", false);
            } else {
                setCopyFeedback("Could not copy automatically. Select and copy the sample text manually.", true);
            }
        });
    }

    var sampleFieldIds = [
        "working_days",
        "periods_per_day",
        "lunch_break_periods",
        "faculty_daily_max_periods",
        "lab_same_day_subject_threshold",
        "rooms",
        "assignments",
        "section_classrooms",
        "faculty_daily_limits",
    ];

    var feasibleSampleDefaults = {};
    sampleFieldIds.forEach(function (id) {
        var field = document.getElementById(id);
        feasibleSampleDefaults[id] = field ? field.value : "";
    });

    // Fallback values for known working configuration.
    if (!feasibleSampleDefaults.working_days) {
        feasibleSampleDefaults.working_days = "5";
    }
    if (!feasibleSampleDefaults.periods_per_day) {
        feasibleSampleDefaults.periods_per_day = "8";
    }
    if (!feasibleSampleDefaults.lunch_break_periods) {
        feasibleSampleDefaults.lunch_break_periods = "5";
    }
    if (!feasibleSampleDefaults.faculty_daily_max_periods) {
        feasibleSampleDefaults.faculty_daily_max_periods = "6";
    }
    if (!feasibleSampleDefaults.lab_same_day_subject_threshold) {
        feasibleSampleDefaults.lab_same_day_subject_threshold = "3";
    }

    function applyFeasibleSample(sampleValues, feedbackMessage) {
        sampleFieldIds.forEach(function (id) {
            var field = document.getElementById(id);
            if (field) {
                field.value = sampleValues[id] || "";
            }
        });

        var workingDaysField = document.getElementById("working_days");
        var periodsField = document.getElementById("periods_per_day");
        var lunchField = document.getElementById("lunch_break_periods");
        var facultyMaxField = document.getElementById("faculty_daily_max_periods");
        var labThresholdField = document.getElementById("lab_same_day_subject_threshold");

        if (workingDaysField) {
            workingDaysField.value = sampleValues.working_days || "5";
        }
        if (periodsField) {
            periodsField.value = sampleValues.periods_per_day || "8";
        }
        if (lunchField) {
            lunchField.value = sampleValues.lunch_break_periods || "5";
        }
        if (facultyMaxField) {
            facultyMaxField.value = sampleValues.faculty_daily_max_periods || "6";
        }
        if (labThresholdField) {
            labThresholdField.value = sampleValues.lab_same_day_subject_threshold || "3";
        }

        var manualSourceOption = document.getElementById("assignment_source_manual");
        if (manualSourceOption) {
            manualSourceOption.checked = true;
        }

        toggleAssignmentSourceUI();
        updateAll();
        setCopyFeedback(feedbackMessage || "Starter dataset loaded.", false);
    }

    var loadSampleButton = document.getElementById("load-feasible-sample");
    if (loadSampleButton) {
        loadSampleButton.addEventListener("click", function () {
            if (!window.fetch) {
                applyFeasibleSample(feasibleSampleDefaults);
                return;
            }

            loadSampleButton.disabled = true;

            fetch("/api/form/feasible-sample", { credentials: "same-origin" })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Failed to load feasible sample");
                    }
                    return response.json();
                })
                .then(function (payload) {
                    var sampleValues = payload && payload.form_values ? payload.form_values : feasibleSampleDefaults;
                    applyFeasibleSample(sampleValues, "Starter dataset loaded.");
                })
                .catch(function () {
                    applyFeasibleSample(feasibleSampleDefaults, "Loaded fallback starter values.");
                })
                .finally(function () {
                    loadSampleButton.disabled = false;
                });
        });
    }

    var loadLargeDemoButton = document.getElementById("load-large-demo-sample");
    if (loadLargeDemoButton) {
        loadLargeDemoButton.addEventListener("click", function () {
            if (!window.fetch) {
                applyFeasibleSample(feasibleSampleDefaults, "Loaded current starter values.");
                return;
            }

            loadLargeDemoButton.disabled = true;

            fetch("/api/form/large-demo-sample", { credentials: "same-origin" })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error("Failed to load large demo sample");
                    }
                    return response.json();
                })
                .then(function (payload) {
                    var sampleValues = payload && payload.form_values ? payload.form_values : feasibleSampleDefaults;
                    applyFeasibleSample(sampleValues, "Feasible benchmark dataset loaded.");
                })
                .catch(function () {
                    applyFeasibleSample(feasibleSampleDefaults, "Loaded current starter values.");
                    setCopyFeedback("Could not load feasible benchmark dataset. Loaded current starter values.", true);
                })
                .finally(function () {
                    loadLargeDemoButton.disabled = false;
                });
        });
    }

    toggleAssignmentSourceUI();
    updateAll();

    document.querySelectorAll("input[name='assignment_source']").forEach(function (field) {
        field.addEventListener("change", function () {
            toggleAssignmentSourceUI();
            updateAll();
        });
    });

    [
        "working_days",
        "periods_per_day",
        "lunch_break_periods",
        "faculty_daily_max_periods",
        "lab_same_day_subject_threshold",
        "rooms",
        "assignments",
        "section_classrooms",
        "faculty_daily_limits",
    ].forEach(function (id) {
        var field = document.getElementById(id);
        if (field) {
            field.addEventListener("input", updateAll);
        }
    });

    var form = document.getElementById("schedule-form");
    if (!form) {
        return;
    }

    form.addEventListener("submit", function (event) {
        var assignmentSource = getAssignmentSource();
        var assignmentMasterCount = parseInt(document.getElementById("assignment_master_count").value || "0", 10);
        var roomsText = getElementValue("rooms");
        var assignmentsText = getElementValue("assignments");
        var homeRoomsText = getElementValue("section_classrooms");
        var facultyLimitsText = getElementValue("faculty_daily_limits");
        var workingDays = parseInt(getElementValue("working_days") || "0", 10);
        var periodsPerDay = parseInt(getElementValue("periods_per_day") || "0", 10);
        var facultyDailyMaxRaw = getElementValue("faculty_daily_max_periods") || "";

        if (Number.isNaN(periodsPerDay) || periodsPerDay <= 0) {
            event.preventDefault();
            alert("Periods per day must be a positive number.");
            return;
        }

        if (Number.isNaN(workingDays) || workingDays < 1 || workingDays > 7) {
            event.preventDefault();
            alert("Working days must be between 1 and 7.");
            return;
        }

        var lunchConfig = parseLunchConfiguration(
            getElementValue("lunch_break_periods"),
            workingDays,
            periodsPerDay
        );
        var lunchError = validateLunchConfiguration(lunchConfig, periodsPerDay);
        if (lunchError) {
            event.preventDefault();
            alert(lunchError);
            return;
        }

        var teachablePerDay = lunchConfig.teachablePerDayMin;
        var facultyDailyMax = parseInt(facultyDailyMaxRaw, 10);
        if (Number.isNaN(facultyDailyMax) || facultyDailyMax <= 0) {
            event.preventDefault();
            alert("Faculty daily max must be a positive number.");
            return;
        }

        if (facultyDailyMax > teachablePerDay) {
            event.preventDefault();
            alert("Faculty daily max cannot exceed available teaching periods per day (" + teachablePerDay + ").");
            return;
        }

        var roomCount = countNonEmptyLines(roomsText);
        var parsedAssignments = parseAssignmentLines(assignmentsText);
        var parsedHomes = parseSectionHomeRooms(homeRoomsText);
        var parsedFacultyLimits = parseFacultyOverrides(facultyLimitsText, teachablePerDay);

        if (roomCount === 0) {
            event.preventDefault();
            alert("Please provide at least one room.");
            return;
        }

        if (assignmentSource === "manual") {
            if (parsedAssignments.rowCount === 0) {
                event.preventDefault();
                alert("Please provide at least one faculty assignment row.");
                return;
            }

            if (parsedAssignments.errors.length > 0) {
                event.preventDefault();
                alert(parsedAssignments.errors[0]);
                return;
            }
        } else {
            if (Number.isNaN(assignmentMasterCount) || assignmentMasterCount <= 0) {
                event.preventDefault();
                alert("Assignment Master has no rows. Add rows in Assignment Master or switch source to Manual.");
                return;
            }
        }

        if (parsedHomes.errors.length > 0) {
            event.preventDefault();
            alert(parsedHomes.errors[0]);
            return;
        }

        if (parsedFacultyLimits.errors.length > 0) {
            event.preventDefault();
            alert(parsedFacultyLimits.errors[0]);
            return;
        }

        var slotsPerSection = calculateSlotsPerSection();
        var globalCapacity = calculateGlobalCapacity(
            slotsPerSection,
            parsedAssignments.sectionCount,
            roomCount
        );

        if (globalCapacity > 0 && parsedAssignments.totalLectures > globalCapacity && parsedAssignments.errors.length === 0) {
            event.preventDefault();
            alert(
                "Total lectures exceed global capacity after lunch breaks. Increase rooms/days/periods or reduce lectures."
            );
        }
    });
});
