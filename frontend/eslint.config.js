import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
    rules: {
      // OWN-005 (SEC-007): tên quán/mô tả là dữ liệu chủ quán gửi lên, tức là
      // không đáng tin. React escape nội dung trong JSX nên hiện tại là an toàn —
      // nhưng "an toàn vì React escape" là giả định, không hiện ra khi review.
      // Chặn thẳng các cửa sổ ra khỏi mô hình đó: nhét HTML thô vào DOM.
      // Muốn hiển thị rich-text thì phải sanitize trước, không bỏ qua cơ chế.
      'no-restricted-syntax': [
        'error',
        {
          selector: 'JSXAttribute[name.name="dangerouslySetInnerHTML"]',
          message: 'Nội dung người dùng không được chạy như HTML — sanitize trước khi render.',
        },
        {
          selector: "MemberExpression[object.name='document'][property.name=/^(inner|outer)HTML$/]",
          message: 'Chèn HTML thô vào DOM là đường XSS — dùng text node của React.',
        },
        {
          selector: 'CallExpression[callee.property.name="insertAdjacentHTML"]',
          message: 'Chèn HTML thô vào DOM là đường XSS.',
        },
        {
          selector: "CallExpression[callee.object.name='document'][callee.property.name='write']",
          message: 'document.write không được dùng trong ứng dụng một trang.',
        },
        {
          selector: 'CallExpression[callee.name="eval"]',
          message: 'eval là đường thoát khỏi mọi kiểm soát nội dung.',
        },
        {
          selector: "CallExpression[callee.type='NewExpression'][callee.callee.name='Function']",
          message: 'new Function là đường thoát khỏi mọi kiểm soát nội dung.',
        },
      ],
    },
  },
])
