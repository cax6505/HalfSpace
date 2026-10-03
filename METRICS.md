# HALFSPACE metrics

This file separates measured contract smoke-test values from metrics that require
annotated broadcast footage. No synthetic value is presented as detector quality.

## Tracking evaluation status

| Metric | Before | After | Dataset / provenance |
| --- | ---: | ---: | --- |
| Ball precision | Not measured | Not measured | SoccerNet or another annotated broadcast clip is not wired yet |
| Ball recall | Not measured | Not measured | SoccerNet or another annotated broadcast clip is not wired yet |
| Ball mean position error (m) | Not measured | Not measured | Requires calibrated ground truth |
| Ball tracked frames | Not measured | Not measured | Requires a real detector run |
| Player ID switches | Not measured | Not measured | Requires a real multi-frame player annotation |

## Contract smoke test

The reproducible command below verifies serialization and metric plumbing on
explicitly labeled sample data:

```bash
/usr/bin/python3 -m tracking.sample --output /tmp/halfspace-sample-tracking.json
```

The generated sample contains 24 frames, 11 players per team, tracked,
interpolated, and lost ball states, and a mean position error of 0.0909 m when
compared with its embedded sample annotations. This is a serialization and UI
contract check, not a broadcast tracking benchmark.

## Performance status

Frontend frame-time and pipeline-stage measurements are not reported yet. The
current playback still renders precomputed sample frames and is not the
60 fps, requestAnimationFrame-driven broadcast renderer required by the product
acceptance checklist.
