# Dependency graph and conflicts

```mermaid
graph TD
  PR1 --> PR2
  PR4 --> PR3
  PR1 --> PR4
  PR2 --> PR4
  PR4 --> PR5
  PR5 --> PR6
  PR5 --> PR7
  PR4 --> PR8
  PR5 --> PR9
  PR6 --> PR9
  PR7 --> PR9
  PR8 --> PR9
  PR4 --> PR10
  PR10 --> PR11
  PR11 --> PR12
  PR10 --> PR13
  PR11 --> PR13
  PR12 --> PR13
  PR4 --> PR14
  PR4 --> PR15
  PR13 --> PR16
  PR4 --> PR17
  PR13 --> PR18
  PR18 --> PR19
  PR14 --> PR19
  PR19 --> PR20
  PR15 --> PR20
  PR20 --> PR21
  PR16 --> PR21
  PR21 --> PR22
  PR22 --> PR23
  PR23 --> PR24
  PR23 --> PR25
  PR23 --> PR26
  PR26 --> PR27
  PR33 --> PR28
  PR33 --> PR29
  PR29 --> PR30
  PR30 --> PR31
  PR30 --> PR32
  PR27 --> PR33
  PR33 --> PR36
  PR36 --> PR37
  PR36 --> PR38
```

#13 supersedes older #10/#11 overlap. #19/#20/#21 reconcile #14/#15/#16. #25 is a sibling, selectively included in the approved font/source chain, not implied by #26 ancestry. #35/#37 are instructions only. #27/#33 are protected manual LLM; #36/#38 stay dormant. #28/#29 share #33 ancestry; #31 and #32 are siblings on #30: keep newer #31 control corrections, add only #32 audit. #9 overlaps #5/#6/#7/#8 and predates shared camera publication; never overwrite its successor source owner. Native enablement and source dependency are separate edges.

Historical stock STOP is HANDLED — DONE / OK per refreshed #31 cab7bab. Older #32 text does not reopen it. Candidate transport/firmware timing is a separate new-version qualification.
