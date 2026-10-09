---
id: platform.story.owner-binds-scenarios-to-suite
type: user_story
system: platform
---

# 属主把场景归入用例组(用户故事)

```gimbal:statement
review: reviewed
id: st.story.bind.1
kind: step
slots:
  cap: cap:suite.create
  order: 1
anchor: US-bind
```

属主新建一个用例组(命名并描述用途)。

```gimbal:statement
review: reviewed
id: st.story.bind.2
kind: step
slots:
  cap: cap:suite.manage_members
  order: 2
anchor: US-bind
```

属主从场景库勾选多个自己的场景,批量加入该组。

```gimbal:statement
review: reviewed
id: st.story.bind.3
kind: step
slots:
  cap: cap:suite.manage_members
  order: 3
anchor: US-bind
```

属主调整成员顺序(影响整组执行的遍历序)。

```gimbal:statement
review: reviewed
id: st.story.bind.4
kind: step
slots:
  cap: cap:suite.manage_members
  order: 4
anchor: US-bind
```

属主移除不需要的成员;场景本身不受影响。

```gimbal:statement
review: reviewed
id: st.story.bind.5
kind: step
slots:
  cap: cap:suite.manage_members
  order: 5
  branch_on: outcome:suite.member_not_owned
anchor: US-bind
```

属主试图把他人场景拉入组时被拒绝(不泄露他人场景的存在性)。
