# 前端功能模块

当前工作台主体仍在 `App.tsx`，`admin/AdminPanel.tsx` 已承载成员与产品分组授权。功能扩展时继续按 `auth`、`hotspots`、`workflows`、`products`、`content`、`agents`、`settings` 拆分页面、数据请求和组件；共享 UI 放 `components/`。不要让页面直接处理产品授权或 Agent 调度规则。
