import type { Page } from '@playwright/test';

const CLOSING = '=== END OF REVIEW ===';

const finding = (severity: string, location: string, what: string, why: string, fix: string) => `- [${severity}] ${location} - What: ${what} Why: ${why} Fix: ${fix}`;

/** Review files in the format of plugins/argani/docs/review-protocol.md, with the variations real files have. */
const CODE_ROUND_1 = [
  'CHANGES the per-commit check (git rebase --exec) corrupts the main repo config',
  finding('Important', '.git-flow/tests/guard.test.sh:6', 'the test runs `git init` and `git config` without unsetting the `GIT_*` variables, so under `git rebase --exec` they act on the **real** repository and write `core.bare=true` into `.git/config`.', 'the spec (AC-7) makes `npm run test:git-flow` the per-commit check; any run of it breaks the main checkout.', 'unset the `GIT_*` variables right after `set -euo pipefail`, then re-run AC-7.'),
  finding('Important', 'package.json:14', 'the root `check` script chains the tools with `;`, so a failing Pint run does not stop the chain.', 'a check that cannot fail gives the approver no evidence.', 'chain with `&&` and add the failing case to the script self-test.'),
  finding('Nit', 'src/phpstan.neon:9', 'the custom rule is registered twice, once by path and once by class name.', 'it runs twice and reports each violation twice.', 'keep the class-name registration only.'),
  finding('Nit', 'CODING.md:112', 'the section names a rule that the ESLint config calls differently.', 'a reader searching the config finds nothing.', 'use the rule id from the config.'),
  finding('Nit', 'docker/app/Dockerfile:41', 'the tools stage installs Composer from the latest tag.', 'a floating tag makes two builds of one commit differ.', 'pin the Composer image to the minor version named in the spec.'),
  CLOSING,
  '',
].join('\n');

const SECURITY_ROUND_1 = [
  'PASS no secret, no new network surface; two hardening notes',
  finding('Nit', 'compose.yaml:122', 'the db service publishes `${FORWARD_DB_PORT:-5432}:5432` on all host interfaces.', 'a copied `.env.example` exposes PostgreSQL with a known password.', 'bind to `127.0.0.1`.'),
  '- [Nit] C:\\work\\app\\settings.ini:3 - What: the file is read with a relative path: see [the note](https://example.test/note). Why: it depends on the working directory. Fix: none needed yet.',
  CLOSING,
  '',
].join('\n');

const COMPLIANCE_ROUND_1 = [
  'CHANGES AC-7 has no literal verify output in build.md',
  finding('Important', 'build.md:288', 'AC-7 is marked done but the log holds a summary, not the literal output and exit status.', 'the approver may accept an AC only with literal output.', 're-run the AC-7 command and paste its output under the AC-7 heading.'),
  '- [Nit] build.md:12 - What: AC-10 is not labelled. Why: the reader must infer the mapping. Fix: put "AC-10:" in front of that block.',
  'Notes: `src/AGENTS.md` and `src/CLAUDE.md` are not committed, each with its own reason.',
  '',
  'Checked against the spec: layout, the **pins** and the AC list.',
  CLOSING,
  '',
].join('\n');

const PASSING = (headline: string, ...lines: string[]) => [`PASS ${headline}`, ...lines, CLOSING, ''].join('\n');

const HUMAN_ROUND_3 = [
  'CHANGES Owner decision after APPROVE of round 2: remove the prepared sets',
  '',
  '- [Important] Remove the prepared sets `if`, `earlyReturn` and `naming` from `src/rector.php`. Rector 2.9.2 no longer applies them.',
  '  - keep `codeQuality` and `codingStyle`',
  '  - update CODING.md in its own commit',
  '',
  '- [Important] Add a rule that rejects `$_`-prefixed names. Why: the owner asked for it.',
  CLOSING,
  '',
].join('\n');

/** Where a review file lives. */
const reviewPath = (round: number, name: string) => `review/round-${round}/review-${name}.md`;

interface RoundSpec {
  round: number;
  /** The verdict state of each reviewer as the task detail reports it. */
  reviews: Record<string, string>;
  /** The text of the reviewer files that exist. */
  texts: Record<string, string>;
}

const ROUND_1: RoundSpec = { round: 1, reviews: { code: 'CHANGES', security: 'PASS', compliance: 'CHANGES' }, texts: { code: CODE_ROUND_1, security: SECURITY_ROUND_1, compliance: COMPLIANCE_ROUND_1 } };

const ROUND_2: RoundSpec = {
  round: 2,
  reviews: { code: 'PASS', security: 'PASS', compliance: 'PASS' },
  texts: { code: PASSING('both Important findings of round 1 are fixed', finding('Nit', 'CODING.md:112', 'the rule id differs.', 'a search finds nothing.', 'use the id from the config.')), security: PASSING('Composer image is pinned; nothing new'), compliance: PASSING('every acceptance criterion has literal evidence') },
};

/** One reviewer has reported, two are still working. */
const ROUND_3_RUNNING: RoundSpec = { round: 3, reviews: { code: 'pending', security: 'PASS', compliance: 'pending' }, texts: { security: PASSING('the request of the owner needs no new exposure', finding('Nit', 'src/rector.php:22', 'the set list changed.', 'a reviewer may expect the old list.', 'none needed.')) } };

/** The owner asked for a change after the approval: the human's file is there, the reviewers have not started. */
const ROUND_3_HUMAN: RoundSpec = { round: 3, reviews: { code: 'pending', security: 'pending', compliance: 'pending', human: 'CHANGES' }, texts: { human: HUMAN_ROUND_3 } };

/**
 * Serves the task `demo/ship-report` with the given rounds: its job files stay, its review files, rounds, models and column
 * are replaced, and every review file the specs name is served. Set up before the page loads, so no poll has to be waited for.
 */
async function mockRounds(page: Page, specs: RoundSpec[], column = 'Review') {
  const files = specs.flatMap((spec) => [
    ...Object.keys(spec.texts).map((name) => ({ path: reviewPath(spec.round, name), group: `Round ${spec.round}`, firstLine: spec.texts[name].split('\n')[0], tone: null })),
    { path: `review/round-${spec.round}/change.diff`, group: `Round ${spec.round}`, firstLine: 'diff --git a/x b/x', tone: null },
  ]);

  await page.route('**/api/tasks/demo/ship-report', async (route) => {
    const task = await (await route.fetch()).json();

    task.column = column;

    task.rounds = specs.map((spec) => ({ n: spec.round, reviews: spec.reviews }));

    task.models = { reviewers: { code: 'opus', security: 'opus', compliance: 'inherit' } };

    task.files = [...task.files.filter((file: { group: string }) => file.group === 'Job'), ...files];

    await route.fulfill({ json: task });
  });

  for (const spec of specs) {
    for (const [name, text] of Object.entries(spec.texts)) {
      await page.route(`**/api/tasks/demo/ship-report/file?path=${encodeURIComponent(reviewPath(spec.round, name))}`, (route) => route.fulfill({ body: text, contentType: 'text/plain' }));
    }
  }
}

export { mockRounds, reviewPath, ROUND_1, ROUND_2, ROUND_3_RUNNING, ROUND_3_HUMAN };
export type { RoundSpec };
