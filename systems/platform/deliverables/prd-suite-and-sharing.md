---
id: platform.prd.suite-and-sharing
type: prd
system: platform
---

# S1 用例组与分享(PRD)

## S1.1 用例组

```gimbal:statement
review: reviewed
id: st.suite.define
kind: define
slots:
  subject: entity:suite
anchor: S1.1
```

用例组(suite)是一组用例的管理与绑定实体:属主把若干自己的场景归入组,按顺序整组执行。

```gimbal:statement
review: reviewed
id: st.suite-member.define
kind: define
slots:
  subject: entity:suite_member
anchor: S1.1
```

组成员(suite_member)是场景在组内的成员关系(含顺序);成员必须是属主自己的场景。

```gimbal:statement
review: reviewed
id: st.suite.rule-owner-only
kind: rule
slots:
  about: cap:suite.run
  violation: outcome:suite.member_not_owned
anchor: S1.1
```

组只能纳入属主自己的场景;试图加入他人场景被拒绝(不泄露存在性)。

## S1.2 分享

```gimbal:statement
review: reviewed
id: st.share.define-ref
kind: define
slots:
  subject: entity:share
anchor: S1.2
```

引用分享(share_ref)是定向、逐次的访问授权:被分享人可读、可执行,但不可写、不可再分享;属主保存即生效(live link)。

```gimbal:statement
review: reviewed
id: st.share.rule-owner-initiates
kind: rule
slots:
  about: cap:share.ref
  violation: outcome:share.admin_proxy_rejected
anchor: S1.2
```

只有属主能发起分享;管理员不可代他人分享(防止借分享转移他人内容)。

```gimbal:statement
review: reviewed
id: st.share.rule-revoke
kind: rule
slots:
  about: cap:share.revoke
  violation: outcome:share.revoked
anchor: S1.2
```

属主可撤销引用(被分享人收到通知);被分享人可退订(不通知属主);撤销与退订均即时生效。

```gimbal:statement
review: reviewed
id: st.share.rule-credential
kind: rule
slots:
  about: cap:share.copy
  violation: outcome:share.credential_missing
anchor: S1.2
```

凭证永不跟随:被分享人执行时按本人凭证池解析,缺失时告警跳过,不存在借用属主凭证的通道。
