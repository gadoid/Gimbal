---
id: platform.story.owner-shares-a-copy
type: user_story
system: platform
---

# 属主拷贝分享(用户故事)

```gimbal:statement
review: reviewed
id: st.story.share-copy.1
kind: step
slots:
  cap: cap:share.copy
  order: 1
anchor: US-copy
```

属主打开分享弹窗,保持默认「副本」模式,选择接收人。

```gimbal:statement
review: reviewed
id: st.story.share-copy.2
kind: step
slots:
  cap: cap:share.copy
  order: 2
anchor: US-copy
```

平台深拷贝资源到接收人名下(场景含数据集;suite 含全部成员),副本写来源三件套(「副本 · 来自某人」)。

```gimbal:statement
review: reviewed
id: st.story.share-copy.3
kind: step
slots:
  cap: cap:share.copy
  order: 3
anchor: US-copy
```

副本完全归接收人:可编辑、可再分享;属主的后续修改不同步、不可撤回。

```gimbal:statement
review: reviewed
id: st.story.share-copy.4
kind: step
slots:
  cap: cap:share.unsubscribe
  order: 4
anchor: US-copy
```

被分享人可把引用转为副本(fork),原引用保留——引用与副本两种状态可并存。
