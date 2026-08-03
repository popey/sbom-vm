#!/usr/bin/env node
// Publish a single GitHub PR review from the structured output of
// `tessl change review run`. The CLI emits review data and never posts to GitHub
// itself; this script turns that data into one `pulls.createReview` call.

import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

function fail(message) {
  throw new Error(message);
}

function env(name, required = true) {
  const value = process.env[name];
  if ((value === undefined || value === '') && required) {
    fail(`missing required env ${name}`);
  }
  return value;
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch (error) {
    fail(`could not read JSON from ${path}: ${error.message}`);
  }
}

function skillDisplayName(ref) {
  const selected = String(ref).split('#').pop();
  const withoutVersion = selected.replace(/@[^/@#]+$/, '');
  const parts = withoutVersion.split('/').filter(Boolean);
  const leaf = parts.at(-1) ?? withoutVersion;
  return leaf === 'SKILL.md' && parts.length > 1 ? parts.at(-2) : leaf;
}

const REVIEW_MARKER = '<!-- tessl-change-review -->';

export function buildReviewRequest(
  review,
  { reviewAction = 'comment', expectedHeadSha } = {},
) {
  if (
    reviewAction !== 'comment' &&
    reviewAction !== 'request-changes-on-findings'
  ) {
    fail(
      `REVIEW_ACTION must be "comment" or "request-changes-on-findings"; got ${JSON.stringify(reviewAction)}`,
    );
  }

  if (typeof expectedHeadSha !== 'string' || expectedHeadSha === '') {
    fail('missing expected head SHA');
  }

  if (!review || typeof review !== 'object') {
    fail('review JSON must be an object');
  }
  if (!review.summary || typeof review.summary !== 'object') {
    fail('review JSON missing object "summary"');
  }
  if (!Array.isArray(review.comments)) {
    fail('review JSON missing array "comments"');
  }
  if (!review.metadata || typeof review.metadata !== 'object') {
    fail('review JSON missing object "metadata"');
  }

  const headSha = review.metadata.headSha;
  if (typeof headSha !== 'string' || headSha === '') {
    fail('review metadata missing string "headSha"');
  }
  if (headSha !== expectedHeadSha) {
    fail(
      `review metadata headSha ${JSON.stringify(headSha)} does not match expected head SHA ${JSON.stringify(expectedHeadSha)}`,
    );
  }
  if (!Array.isArray(review.metadata.skills)) {
    fail('review metadata missing array "skills"');
  }
  if (typeof review.summary.overview !== 'string') {
    fail('review summary missing string "overview"');
  }
  if (!Array.isArray(review.summary.warnings)) {
    fail('review summary missing array "warnings"');
  }
  if (!Array.isArray(review.summary.unplacedFindings)) {
    fail('review summary missing array "unplacedFindings"');
  }

  const overview = review.summary.overview
    .trim()
    .replace(/^#{1,6}\s+findings\s*\n+/i, '')
    .trim();

  const warnings = review.summary.warnings;
  const unplacedFindings = review.summary.unplacedFindings;
  const skillNames = review.metadata.skills.map(skillDisplayName);
  const skillLine =
    skillNames.length > 0
      ? `Reviewed against skills: ${skillNames.map((name) => `\`${name}\``).join(', ')}`
      : 'Reviewed against skills: _none reported_';

  const bodyParts = [REVIEW_MARKER, '## tessl change review:', skillLine];
  bodyParts.push(
    overview === '' ? '_No summary was produced for this diff._' : overview,
  );

  if (unplacedFindings.length > 0) {
    const items = unplacedFindings.map((finding, index) => {
      if (!finding || typeof finding !== 'object') {
        fail(`summary.unplacedFindings[${index}] is not an object`);
      }
      const locationParts = [];
      if (finding.path) locationParts.push(finding.path);
      if (finding.line) locationParts.push(`line ${finding.line}`);
      if (finding.side) locationParts.push(finding.side);
      const where =
        locationParts.length > 0 ? ` \`${locationParts.join(':')}\`` : '';
      const reason = finding.reason ? ` (${finding.reason})` : '';
      const lines = [`- **Unplaced finding**${where}${reason}`];
      for (const bodyLine of String(finding.body ?? '').split('\n')) {
        lines.push(`  ${bodyLine}`);
      }
      return lines.join('\n');
    });

    bodyParts.push(
      [
        '<details>',
        `<summary>Unplaced findings (${unplacedFindings.length}) — could not anchor to a changed hunk</summary>`,
        '',
        items.join('\n'),
        '</details>',
      ].join('\n'),
    );
  }

  if (warnings.length > 0) {
    bodyParts.push(
      [
        '<details>',
        `<summary>Warnings (${warnings.length})</summary>`,
        '',
        warnings.map((warning) => `- ${warning}`).join('\n'),
        '</details>',
      ].join('\n'),
    );
  }

  bodyParts.push(
    '---\nTo trigger a re-review write a comment that says `@tessl-change-review`.',
  );
  const body = bodyParts.join('\n\n');

  const comments = review.comments.map((commentInput, index) => {
    if (!commentInput || typeof commentInput !== 'object') {
      fail(`comments[${index}] is not an object`);
    }
    if (typeof commentInput.path !== 'string' || commentInput.path === '') {
      fail(`comments[${index}] missing string "path"`);
    }
    if (!Number.isInteger(commentInput.line) || commentInput.line < 1) {
      fail(`comments[${index}] "line" must be a positive integer`);
    }
    if (commentInput.side !== 'LEFT' && commentInput.side !== 'RIGHT') {
      fail(`comments[${index}] "side" must be LEFT or RIGHT`);
    }
    if (typeof commentInput.body !== 'string' || commentInput.body === '') {
      fail(`comments[${index}] missing string "body"`);
    }

    const comment = {
      path: commentInput.path,
      line: commentInput.line,
      side: commentInput.side,
      body: commentInput.body,
    };

    if (commentInput.startLine !== undefined) {
      if (!Number.isInteger(commentInput.startLine) || commentInput.startLine < 1) {
        fail(`comments[${index}] "startLine" must be a positive integer`);
      }
      if (commentInput.startLine >= commentInput.line) {
        fail(`comments[${index}] "startLine" must be less than "line"`);
      }
      if (commentInput.startSide !== 'LEFT' && commentInput.startSide !== 'RIGHT') {
        fail(
          `comments[${index}] "startSide" is required and must be LEFT or RIGHT when "startLine" is set`,
        );
      }
      comment.start_line = commentInput.startLine;
      comment.start_side = commentInput.startSide;
    } else if (commentInput.startSide !== undefined) {
      fail(`comments[${index}] "startSide" requires "startLine"`);
    }

    return comment;
  });

  const hasFindings = comments.length > 0 || unplacedFindings.length > 0;
  const event =
    reviewAction === 'request-changes-on-findings' && hasFindings
      ? 'REQUEST_CHANGES'
      : 'COMMENT';

  return {
    headSha,
    event,
    commentCount: comments.length,
    payload: {
      commit_id: headSha,
      event,
      body,
      comments,
    },
  };
}

export async function main() {
  const REPO = env('REPO');
  const PR_NUMBER = env('PR_NUMBER');
  const GH_TOKEN = env('GH_TOKEN');
  const EXPECTED_HEAD_SHA = env('EXPECTED_HEAD_SHA');
  const REVIEW_OUTPUT = env('REVIEW_OUTPUT', false) ?? 'change-review.json';
  const OUT = env('OUT', false) ?? 'review-publish.json';
  const REVIEW_ACTION = env('REVIEW_ACTION', false) ?? 'comment';

  if (!/^\d+$/.test(PR_NUMBER) || Number(PR_NUMBER) < 1) {
    fail(`PR_NUMBER must be a positive integer; got ${JSON.stringify(PR_NUMBER)}`);
  }

  const [owner, repo, ...rest] = REPO.split('/');
  if (rest.length > 0 || !owner || !repo) {
    fail(`REPO must be "owner/repo"; got ${JSON.stringify(REPO)}`);
  }

  const review = readJson(REVIEW_OUTPUT);
  const { headSha, event, commentCount, payload } = buildReviewRequest(review, {
    reviewAction: REVIEW_ACTION,
    expectedHeadSha: EXPECTED_HEAD_SHA,
  });

  const response = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/pulls/${PR_NUMBER}/reviews`,
    {
      method: 'POST',
      headers: {
        accept: 'application/vnd.github+json',
        authorization: `Bearer ${GH_TOKEN}`,
        'content-type': 'application/json',
        'x-github-api-version': '2022-11-28',
      },
      body: JSON.stringify(payload),
    },
  );

  const text = await response.text();
  if (!response.ok) {
    fail(`GitHub createReview failed (HTTP ${response.status}): ${text}`);
  }

  let created;
  try {
    created = JSON.parse(text);
  } catch (error) {
    fail(`could not parse GitHub createReview response: ${error.message}`);
  }

  writeFileSync(
    OUT,
    `${JSON.stringify(
      {
        reviewId: created.id ?? null,
        reviewUrl: created.html_url ?? null,
        commitId: headSha,
        event,
        commentCount,
      },
      null,
      2,
    )}\n`,
  );

  console.error(
    `publish-review.mjs: created review ${created.id ?? '(unknown id)'}`,
  );
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(`publish-review.mjs: ${error.message}`);
    process.exitCode = 1;
  });
}
