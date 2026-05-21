// flow G: backend recovery semantics - orphan a running scan and confirm it
// transitions to a clean failed state instead of staying stuck.
import {
  test,
  expect,
  resetState,
  seedUser,
  startScanViaApi,
  getScan,
  orphanRunningScans,
} from "./helpers/flow.js";

test.describe("flow G - recovery", () => {
  test("running scans get cleaned up after a simulated restart", async ({ request, context }) => {
    await resetState(request);
    const seed = await seedUser(request, context);

    // start a scan but do NOT finalize it - leaves the row in pending/running
    const scan = await startScanViaApi(request, seed.repo_id);
    const beforeOrphan = await getScan(request, scan.id);
    expect(["pending", "running"]).toContain(beforeOrphan.status);

    // simulate a restart by failing in-flight scans
    const out = await orphanRunningScans(request);
    expect(out.orphaned).toBeGreaterThanOrEqual(1);

    const afterOrphan = await getScan(request, scan.id);
    expect(afterOrphan.status).toBe("failed");
    expect(afterOrphan.error || "").toMatch(/orphan/i);
  });
});
