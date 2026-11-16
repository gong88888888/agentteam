/**
 * Harness 状态机运行器
 * 根据状态机定义驱动任务状态流转
 */
class StateMachineRunner {
  constructor(definition) {
    this.def     = definition;
    this.current = definition.initial;
  }

  /** 触发事件，返回新状态（或 null 表示无效转换） */
  transition(event) {
    const state = this.def.states[this.current];
    if (!state || !state.on) return null;
    const next = state.on[event];
    if (!next || !this.def.states[next]) return null;
    this.current = next;
    return this.current;
  }

  isFinal() {
    const state = this.def.states[this.current];
    return state?.type === 'final';
  }

  getOnEntry() {
    return this.def.states[this.current]?.onEntry || null;
  }

  getLabel() {
    return this.def.states[this.current]?.label || this.current;
  }
}

module.exports = StateMachineRunner;
