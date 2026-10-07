---
id: platform.endpoint_catalog.get_by_endpoint_id_full
type: endpoints
system: platform
service: platform-service
---

# Get Full Endpoint

```gimbal:endpoint
review: reviewed
id: platform.endpoint_catalog.get_by_endpoint_id_full
system: platform
service: platform-service
name: Get Full Endpoint
description: 'Proxy ``GET {plate}/api/endpoint/{id}/full``.


  走 ``plate_client.get_endpoint_full`` —— 与 dispatch 侧**同一条缓存条目**,

  故编辑器浏览与 dispatch 判定看到的是**同一份快照**(阶段二·① I)。超时随之

  统一为那条软取的 3s(``DECLARED_PATHS_TIMEOUT_SEC``),不再是

  ``PLATE_TIMEOUT_SEC`` 的 30s。


  返回 = plate 的 item **原样** + 一个后端算好的 ``declared_surface``:

  声明侧可注入面的**扁平字符串集合**(归一化、容器前缀、模板形态全部展开)。

  前端据此不再自己算声明半(§2.2)。item 另有消费者(候选树 UI),故**只增

  字段、不裁 item**;展开成新 dict 而非就地改 —— 缓存里那份 item 是进程级

  共享只读面(``EndpointFull.item`` 的契约)。


  ``declared_surface`` 为 ``None`` ⇒ 该端点的**声明面**不可解析(降级),前端

  从严只认 body 面。**不用 [] 冒充**:空目录(真无声明,给 ``["$"]``)与降级

  是两件事。契约 item 本身不可得时本路由直接 502/404,客户端看不到这个字段。


  item 只要是 dict 就原样透传(**空 item ``{}`` 也算**):它得到一个空声明树

  与 ``["$"]``,不视为错误 —— 不得用真值判等把 ``{}`` 并成 ``None``(§5)。'
binding:
  protocol: http
  method: GET
  path: /api/endpoint-catalog/{endpoint_id}/full
  auth: bearer
  body_type: none
request: {}
responses:
  '200':
    description: Successful Response
metadata:
  module: endpoint-catalog
  tags:
  - platform
  owner: gimbal-bootstrap
```
