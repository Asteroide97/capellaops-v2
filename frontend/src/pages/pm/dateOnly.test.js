import assert from "node:assert/strict";
import test from "node:test";

import { formatPmCalendarDate, pmCalendarDayNumber, toPmDateInputValue } from "./dateOnly.js";

test("PM date-only values keep the selected calendar day in display and edit inputs", () => {
  for (const value of ["2026-10-01", "2026-01-01", "2026-12-31"]) {
    assert.equal(toPmDateInputValue(value), value);
    assert.notEqual(formatPmCalendarDate(value), "—");
  }

  assert.match(formatPmCalendarDate("2026-10-01").toLowerCase(), /1 oct 2026/);
  assert.equal(pmCalendarDayNumber("2026-10-01") - pmCalendarDayNumber("2026-09-30"), 1);
  assert.equal(toPmDateInputValue("2026-10-01T00:00:00Z"), "");
  assert.equal(formatPmCalendarDate("2026-02-31"), "—");
});
