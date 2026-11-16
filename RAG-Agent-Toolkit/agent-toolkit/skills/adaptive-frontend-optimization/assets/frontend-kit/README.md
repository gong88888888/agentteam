# Adaptive Frontend Kit

零运行时依赖、ES module、Node 18+ 测试。适用于 Vue/React/原生页面的可选基础能力，不是新的组件框架。代码为本次原创，没有复制上游组件。目录可以独立迁移；使用宿主已有同等能力时不要重复引入。

在此目录运行 `npm test`。宿主按需相对导入 `index.js` 和 `layout.css`，或通过本地 package 安装。CSS 仅作用于显式添加的 `af-*` 类，不自动修改页面。旧浏览器不支持 container query 时保留单列。

## 最新结果与预览生命周期

```js
import { createLatestTask, createObjectUrlPool } from './index.js';
const task = createLatestTask();
const urls = createObjectUrlPool();
async function loadPreview(endpoint) {
  const result = await task.run(async signal => {
    const response = await fetch(endpoint, { signal });
    if (!response.ok) throw new Error(`Preview failed: ${response.status}`);
    return response.blob();
  });
  if (result.status === 'discarded') return;
  // Only accepted results allocate URLs; stale requests cannot leak them.
  const nextUrl = urls.create(result.value);
  // Update the host image, then release its previous URL after replacement.
  return nextUrl;
}
function cleanup() { task.dispose(); urls.dispose(); }
// Vue: onUnmounted(cleanup). React: return cleanup from the owning effect.
```

调用方负责把成功结果写入响应式状态、显示当前错误，并在替换预览后 `urls.release(previousUrl)`。不要在 work 内修改页面；最新结果保护只作用于返回值。dispose 后不可复用，重新挂载时重新创建。

`cancel` 请求传输中止并使结果失效，但不能强行终止忽略 signal 的 Promise，也不会撤销服务端写操作。最新请求失败时会抛出原始错误；过期请求成功或失败均返回 discarded。

## 布局与诊断

```html
<section class="af-scope">
  <div class="af-split">
    <aside class="af-wrap">Configuration</aside>
    <main class="af-wrap">Task content</main>
  </div>
</section>
```

宿主可设置 `--af-gap`、`--af-focus`、`--af-media-ratio`。按钮使用已有图标库、可访问名称与 tooltip；库不提供替代控件。850px 是这个两栏配方的初始容器阈值，需按内容调整，不是通用设备标准。

浏览器中调用 `inspectOverflow(document.documentElement)` 获取候选元素。可滚动且有 `data-af-scroll-reason="Template thumbnails"` 的元素标为 expected；不能用此属性豁免 hidden 裁切。探针不检测所有遮挡、变换、纵向裁切、对比度、焦点陷阱或屏幕阅读器问题，仍需实际浏览器截图及人工检查。测试中的 DOM 替身只验证分类逻辑，不代表 CSS 已通过浏览器验收。
