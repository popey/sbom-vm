import assert from 'node:assert/strict';
import test from 'node:test';

import { buildReviewRequest } from './publish-review.mjs';

const HEAD_SHA = '0123456789abcdef0123456789abcdef01234567';

function reviewFixture(overrides = {}) {
  const { summary = {}, metadata = {}, ...rest } = overrides;
  return {
    summary: {
      overview: '## Findings\n\nEverything is clear.',
      warnings: [],
      unplacedFindings: [],
      ...summary,
    },
    comments: [],
    metadata: {
      headSha: HEAD_SHA,
      skills: ['tessl/code-review#review-security-risks'],
      ...metadata,
    },
    ...rest,
  };
}

test('builds a comment review with ranges and summary details', () => {
  const review = reviewFixture({
    summary: {
      overview: '## Findings\n\nEverything is clear.',
      warnings: ['One warning'],
      unplacedFindings: [
        {
          path: 'sbom-vm.py',
          line: 10,
          side: 'RIGHT',
          reason: 'outside changed hunk',
          body: 'Unplaced body',
        },
      ],
    },
    comments: [
      {
        path: 'sbom-vm.py',
        startLine: 3,
        startSide: 'RIGHT',
        line: 5,
        side: 'RIGHT',
        body: 'Inline body',
      },
    ],
  });

  const result = buildReviewRequest(review, {
    expectedHeadSha: HEAD_SHA,
  });

  assert.equal(result.event, 'COMMENT');
  assert.equal(result.commentCount, 1);
  assert.equal(result.payload.commit_id, HEAD_SHA);
  assert.deepEqual(result.payload.comments, [
    {
      path: 'sbom-vm.py',
      start_line: 3,
      start_side: 'RIGHT',
      line: 5,
      side: 'RIGHT',
      body: 'Inline body',
    },
  ]);
  assert.match(result.payload.body, /Reviewed against skills: `review-security-risks`/);
  assert.match(result.payload.body, /Everything is clear\./);
  assert.doesNotMatch(result.payload.body, /## Findings/);
  assert.match(result.payload.body, /Unplaced findings \(1\)/);
  assert.match(result.payload.body, /One warning/);
});

test('only requests changes when blocking mode has findings', () => {
  const noFindings = buildReviewRequest(reviewFixture(), {
    reviewAction: 'request-changes-on-findings',
    expectedHeadSha: HEAD_SHA,
  });
  assert.equal(noFindings.event, 'COMMENT');

  const withFinding = buildReviewRequest(
    reviewFixture({
      comments: [
        {
          path: 'sbom-vm.py',
          line: 5,
          side: 'RIGHT',
          body: 'Finding',
        },
      ],
    }),
    {
      reviewAction: 'request-changes-on-findings',
      expectedHeadSha: HEAD_SHA,
    },
  );
  assert.equal(withFinding.event, 'REQUEST_CHANGES');

  const withUnplacedFinding = buildReviewRequest(
    reviewFixture({
      summary: {
        unplacedFindings: [
          {
            path: 'sbom-vm.py',
            line: 5,
            side: 'RIGHT',
            body: 'Unplaced finding',
          },
        ],
      },
    }),
    {
      reviewAction: 'request-changes-on-findings',
      expectedHeadSha: HEAD_SHA,
    },
  );
  assert.equal(withUnplacedFinding.event, 'REQUEST_CHANGES');
  assert.equal(withUnplacedFinding.commentCount, 0);
});

test('rejects a review generated for a different head SHA', () => {
  assert.throws(
    () =>
      buildReviewRequest(reviewFixture(), {
        expectedHeadSha: 'ffffffffffffffffffffffffffffffffffffffff',
      }),
    /does not match expected head SHA/,
  );
});

test('requires startSide for a multi-line comment', () => {
  assert.throws(
    () =>
      buildReviewRequest(
        reviewFixture({
          comments: [
            {
              path: 'sbom-vm.py',
              startLine: 3,
              line: 5,
              side: 'RIGHT',
              body: 'Finding',
            },
          ],
        }),
        { expectedHeadSha: HEAD_SHA },
      ),
    /"startSide" is required/,
  );
});

test('rejects a non-decreasing multi-line range', () => {
  assert.throws(
    () =>
      buildReviewRequest(
        reviewFixture({
          comments: [
            {
              path: 'sbom-vm.py',
              startLine: 5,
              startSide: 'RIGHT',
              line: 5,
              side: 'RIGHT',
              body: 'Finding',
            },
          ],
        }),
        { expectedHeadSha: HEAD_SHA },
      ),
    /"startLine" must be less than "line"/,
  );
});

test('rejects startSide without startLine', () => {
  assert.throws(
    () =>
      buildReviewRequest(
        reviewFixture({
          comments: [
            {
              path: 'sbom-vm.py',
              startSide: 'RIGHT',
              line: 5,
              side: 'RIGHT',
              body: 'Finding',
            },
          ],
        }),
        { expectedHeadSha: HEAD_SHA },
      ),
    /"startSide" requires "startLine"/,
  );
});
