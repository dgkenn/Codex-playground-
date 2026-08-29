// Config for the build's own undeclared-identifier check — see build-coach.mjs.
//
// This is the check that would have caught `govern`: a name read inside a boolean expression,
// never declared as a parameter, never assigned anywhere, silently correct until the branch that
// reaches it finally runs. `no-undef` catches that class of bug by construction — it does not need
// to know what the code means, only that every name it reads was declared somewhere reachable.
//
// The globals below are the actual browser APIs this page calls by their bare names. Keeping the
// list explicit rather than reaching for an `env: browser` preset is deliberate: a preset accepts
// hundreds of names this page has never heard of, which quietly widens exactly what this check is
// for — catching a name that should not resolve. Adding a real new API call means adding it here,
// which is the point, not friction.
export default [
  {
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'script',
      globals: {
        window: 'readonly', document: 'readonly', navigator: 'readonly', localStorage: 'readonly',
        console: 'readonly', fetch: 'readonly', setTimeout: 'readonly', clearTimeout: 'readonly',
        setInterval: 'readonly', clearInterval: 'readonly', Image: 'readonly',
        SpeechSynthesisUtterance: 'readonly', speechSynthesis: 'readonly', Audio: 'readonly',
        DataView: 'readonly', Uint8Array: 'readonly', ArrayBuffer: 'readonly', btoa: 'readonly',
        requestAnimationFrame: 'readonly', getComputedStyle: 'readonly', location: 'readonly',
        history: 'readonly', addEventListener: 'readonly', removeEventListener: 'readonly',
        performance: 'readonly', URL: 'readonly', Blob: 'readonly', TextEncoder: 'readonly',
        TextDecoder: 'readonly', crypto: 'readonly', alert: 'readonly', confirm: 'readonly',
        prompt: 'readonly', screen: 'readonly', isFinite: 'readonly', isNaN: 'readonly',
        parseInt: 'readonly', parseFloat: 'readonly', devicePixelRatio: 'readonly',
      },
    },
    rules: { 'no-undef': 'error' },
  },
];
