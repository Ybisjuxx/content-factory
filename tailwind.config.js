/** Tailwind is compiled ahead of time (npm run build:css) so the dashboard works offline.
 *  The previous Play CDN (cdn.tailwindcss.com) rendered an unstyled page without internet. */
module.exports = {
  content: ['./web/index.html'],
  theme: { extend: {} },
  plugins: [],
};
