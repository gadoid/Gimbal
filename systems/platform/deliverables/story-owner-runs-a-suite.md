---
id: platform.story.owner-runs-a-suite
type: user_story
system: platform
---

# 属主整组执行用例组(用户故事)

```gimbal:statement
review: reviewed
id: st.story.run-suite.1
kind: step
slots:
  cap: cap:suite.run
  order: 1
anchor: US-run
```

属主点击「运行整组」,平台按成员顺序逐个发起执行(每成员用其默认方案)。

```gimbal:statement
review: reviewed
id: st.story.run-suite.2
kind: step
slots:
  cap: cap:suite.run
  order: 2
anchor: US-run
```

执行跳转到批次视图;全部成员的执行按 batch_id 归并为一条通知。

```gimbal:statement
review: reviewed
id: st.story.run-suite.3
kind: step
slots:
  cap: cap:suite.run
  order: 3
anchor: US-run
```

单个成员校验失败时跳过并给出原因;其余成员不受影响。

```gimbal:statement
review: reviewed
id: st.story.run-suite.4
kind: step
slots:
  cap: cap:suite.run
  order: 4
  branch_on: outcome:suite.run_in_progress
anchor: US-run
```

属主在该组有未终态批次时再次发起,收到 409 附本人批次深链(防重按人)。
