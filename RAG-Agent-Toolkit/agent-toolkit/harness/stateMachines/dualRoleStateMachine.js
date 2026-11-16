/**
 * 双 AI 角色状态机定义
 * 描述双角色协作的完整状态流转
 */
const stateMachine = {
  id: 'dualRole',
  initial: 'idle',
  states: {
    idle: {
      on: { START: 'roleA_executing' }
    },
    roleA_executing: {
      label: '角色A 执行中',
      onEntry: 'executeRoleA',
      on: {
        SUCCESS:  'roleB_reviewing',
        FAILURE:  'retrying_roleA'
      }
    },
    retrying_roleA: {
      label: '角色A 重试中',
      onEntry: 'retryRoleA',
      on: {
        SUCCESS: 'roleB_reviewing',
        FAILURE: 'failed'
      }
    },
    roleB_reviewing: {
      label: '角色B 审核中',
      onEntry: 'executeRoleB',
      on: {
        ACCEPT:  'saving',
        REVISE:  'roleA_revising',
        FAILURE: 'failed'
      }
    },
    roleA_revising: {
      label: '角色A 修订中',
      onEntry: 'reviseRoleA',
      on: {
        SUCCESS: 'roleB_reviewing',
        FAILURE: 'failed'
      }
    },
    saving: {
      label: '保存结果',
      onEntry: 'saveResult',
      on: {
        SUCCESS: 'completed',
        FAILURE: 'failed'
      }
    },
    completed: { type: 'final', label: '完成' },
    failed:    { type: 'final', label: '失败' }
  }
};

module.exports = stateMachine;
