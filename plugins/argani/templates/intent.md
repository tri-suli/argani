# Intent: {{title}}

Author: {{name}}
Status: draft
Type: {{job type}}
Number: {{n}}
Risk: {{low | medium | high}}
Date: {{YYYY-MM-DD}}

<!-- Type is one of branchTypes in the project's configuration (project.json in the argani home). It fills {type} in the job
     branch and picks the base branch. Delete the Type line when no branchTypes are set.
     Number is the job number that fills {n} in the job branch; it comes from next_number.py, is
     assigned once and never changed. Delete the Number line when branchPattern has no {n}.
     Risk is low, medium or high (medium when the line is missing). It picks the models of the
     builder and the reviewers through agentModels; a human sets it when approving the intent.
     Status is "draft" until a human approves it with /argani:intent approve {{slug}}.
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

<!-- Every item must use this exact shape, numbered 1, 2, 3 in order, with a verification that
     someone can run or do. Item n is referred to as AC-n in the spec, build, reviews and decision:
     1. [ ] {{claim}} — verify: {{command | test | named manual step}}
     A criterion only a human can check (judgement, data that stays on someone's machine) reads
     `verify: manual: <who does what>`; it becomes a checklist item in the merge request.
     Intent without verifiable criteria cannot be approved. -->

1. [ ] {{claim}} — verify: {{command | test | named manual step}}

## Out of scope

<!-- What this work deliberately does not do. -->

- {{excluded item}}

## Open questions

<!-- Unknowns the human must answer or the spec must resolve. Write "None" if empty. -->

- {{question}}
