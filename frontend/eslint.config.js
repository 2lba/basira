import js from "@eslint/js";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

const unusedArgsIgnoreUnderscore = {
  "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
};

export default [
  {
    ignores: [
      "dist/**",
      "build/**",
      "node_modules/**",
      "e2e/node_modules/**",
      "e2e/test-results/**",
      "e2e/playwright-report/**",
    ],
  },
  js.configs.recommended,
  {
    files: ["src/**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.browser },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
    },
    settings: { react: { version: "19.0" } },
    rules: {
      "react/jsx-uses-react": "off",
      "react/react-in-jsx-scope": "off",
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      ...unusedArgsIgnoreUnderscore,
    },
  },
  // node-side tooling: vite config, the eslint config itself
  {
    files: ["vite.config.js", "eslint.config.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.node },
    },
    rules: { ...unusedArgsIgnoreUnderscore },
  },
  // playwright e2e suite runs in node but the test bodies poke at browser
  // globals through the `page` fixture - keep both sets available.
  {
    files: ["e2e/**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      globals: { ...globals.node, ...globals.browser },
    },
    rules: { ...unusedArgsIgnoreUnderscore },
  },
];
