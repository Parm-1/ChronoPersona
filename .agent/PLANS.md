# Active Plans

The scorer plan owns the current E5 evidence change. Its closure condition is
green exact-head CI; once that condition is satisfied it is complete and no
plan is write-active until the measurement-reliability successor is created:

- `.agent/plans/active-verified-registry-scoring.md` — publish the accepted
  repeated Pythia scorer evidence, current-state reconciliation, and
  stable-read portability fix, then require exact-head CI without rerunning the
  completed target gate.

Completed plans remain under `.agent/plans/` as durable history. In particular,
`active-pythia-local-feasibility.md` records the completed v0/v1 loading and
tiny-LoRA feasibility work. `active-verified-registry-loader.md` records the
completed exact-snapshot tokenizer-loader gate through green evidence head
`dd0b564` on draft PR #33. Neither completed plan is write-active.
