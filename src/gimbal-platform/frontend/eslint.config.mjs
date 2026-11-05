// eslint.config.mjs — 前端 lint 门禁(2026-11-05 前端评审 P3-14)。
//
// 范围刻意收窄到「正确性」:只开 eslint-plugin-vue 的 essential 一族
// (真错误:重复 key、非法 v-model、mutating props、未定义组件等),
// 不做风格审判 —— 风格归 prettier/设计系统管,lint 只回答「这段代码
// 有没有错」。评审用临时脚本预跑过同一套:除 20 处有意为之的「props
// 拷贝成本地状态 + watch 同步」外全绿,所以 vue/no-mutating-props 降
// warn(该模式是各表单的既定手法,不是缺陷)。
//
// TS 文件只过解析不开 typescript-eslint 规则:类型面已由 vue-tsc
// (strict + noUnusedLocals)全量把守,再叠一层类型 lint 是重复门禁。
import pluginVue from 'eslint-plugin-vue'
import tsParser from '@typescript-eslint/parser'

export default [
  {
    ignores: [
      'dist/**', 'node_modules/**', 'coverage/**',
      // M2 生成物(脚本产出、带哈希头,禁手改)— lint 不该逼人改生成文件
      'src/types/m2.ts',
    ],
  },
  ...pluginVue.configs['flat/essential'],
  {
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: tsParser } },
  },
  {
    files: ['**/*.ts'],
    languageOptions: { parser: tsParser },
  },
  {
    rules: {
      // 既定手法:表单本地草稿 + watch 回写,不是真缺陷(见文件头)
      'vue/no-mutating-props': 'warn',
      // ui 基元(Button/Table/Dialog…)与路由视图(Auths/Login/Runner…)
      // 单词名是本库既定命名,不按 Vue 官方多词建议改
      'vue/multi-word-component-names': 'off',
      // 对模板里 TS 断言的联合类型(as A | B)误报成 Vue2 filter 语法;
      // 真 filter 写法在 Vue3 编译期就会报错,轮不到 lint
      'vue/no-deprecated-filter': 'off',
    },
  },
]
