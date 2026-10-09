---
id: platform.story.owner-shares-by-reference
type: user_story
system: platform
---

# 属主以引用分享(用户故事)

```gimbal:statement
review: reviewed
id: st.story.share-ref.1
kind: step
slots:
  cap: cap:share.ref
  order: 1
anchor: US-ref
```

属主打开分享弹窗,选择「引用」模式和接收人。

```gimbal:statement
review: reviewed
id: st.story.share-ref.2
kind: step
slots:
  cap: cap:share.ref
  order: 2
anchor: US-ref
```

被分享人在「共享给我的」分区看到资源,可读定义、方案、数据集并执行,但不可写、不可再分享。

```gimbal:statement
review: reviewed
id: st.story.share-ref.3
kind: step
slots:
  cap: cap:suite.run
  order: 3
anchor: US-ref
```

被分享人 run 引用的 suite:引用覆盖其全部成员,循环内逐成员检查执行权。

```gimbal:statement
review: reviewed
id: st.story.share-ref.4
kind: step
slots:
  cap: cap:share.revoke
  order: 4
anchor: US-ref
```

属主保存被引用的资源;被分享人立即看到新内容(保存提示已告知属主名单)。

```gimbal:statement
review: reviewed
id: st.story.share-ref.5
kind: step
slots:
  cap: cap:share.revoke
  order: 5
anchor: US-ref
```

属主撤销引用,被分享人收到通知且下一次访问即失效;被分享人也可自行退订(不通知属主)。
