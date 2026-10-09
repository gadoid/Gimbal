---
id: platform.dict.share
type: dictionary
system: platform
---

# 分享词条

```gimbal:term
- review: reviewed
  id: entity:share
  label: 分享
  gloss: 属主把场景或用例组定向分享给他人;引用(live link)与副本(独立拷贝)两种模式
- review: reviewed
  id: cap:share.ref
  label: 发起引用分享
  gloss: 仅属主(admin 不可代发);幂等 upsert;每人上限 SHARE_REF_CAP
- review: reviewed
  id: cap:share.copy
  label: 拷贝分享
  gloss: 深拷贝到接收人名下(场景含数据集/suite 含成员);不可撤回
- review: reviewed
  id: cap:share.revoke
  label: 撤销引用
  gloss: 属主(通知被分享人)/admin(入审计);即时生效
- review: reviewed
  id: cap:share.unsubscribe
  label: 退订引用
  gloss: 被分享人删自己的引用行;不通知属主;可随时重新被分享
- review: reviewed
  id: outcome:share.received
  label: 收到分享
  gloss: 引用(share_ref_received)与副本(resource_handoff)两种通知
- review: reviewed
  id: outcome:share.revoked
  label: 引用已撤销
  gloss: 属主撤销或 admin 治理撤销后,被分享人收到通知且下次访问即失效
- review: reviewed
  id: outcome:share.admin_proxy_rejected
  label: 管理员代发被拒
  gloss: admin 不可替他人分享(§8.1;防止借分享转移他人内容)
- review: reviewed
  id: outcome:share.credential_missing
  label: 凭证缺失
  gloss: 被分享人执行时按本人池解析,缺凭证以明确原因失败(凭证永不跟随)
```
