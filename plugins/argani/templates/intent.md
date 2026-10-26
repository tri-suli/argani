# Intent: {{title}}

Author: {{name}}
Status: draft
Date: {{YYYY-MM-DD}}

<!-- Status is "draft" until a human approves it with /argani:intent approve {{slug}}.
     The approved form is: Status: approved by {{name}} on {{YYYY-MM-DD}} -->

## Problem

<!-- What is wrong or missing today, and for whom. Facts, not solutions. -->

{{problem}}

## Desired outcome

<!-- What "better" looks like once this is done. -->

{{outcome}}

## Affected users and systems

<!-- Who and what is touched: people, repositories, services, documents. -->

- {{user or system}}

## Constraints

<!-- Rules the work must respect: policies, deadlines, compatibility, cost. -->

- {{constraint}}

## Acceptance criteria

<!-- Every item must use this exact shape, with a verification that someone can run or do:
     - AC-1: {{claim}} — verify: {{command | test | named manual step}}
     Intent without verifiable criteria cannot be approved. -->

- AC-1: {{claim}} — verify: {{command | test | named manual step}}

## Out of scope

<!-- What this work deliberately does not do. -->

- {{excluded item}}

## Open questions

<!-- Unknowns the human must answer or the spec must resolve. Write "None" if empty. -->

- {{question}}
