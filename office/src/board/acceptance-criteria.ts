import { CHECKED_BOX, CRITERION_PATTERN, MANUAL_PREFIX_PATTERN } from '@/constants/document';
import type { ParsedCriterion } from '@/types/document';

/** Reads one acceptance criterion in the format plugins/argani/scripts/artifact_check.py enforces; anything else is null. */
class AcceptanceCriteria {
  parse(line: string): ParsedCriterion | null {
    const match = CRITERION_PATTERN.exec(line);

    if (match === null) {
      return null;
    }

    const verify = match[4].trim();

    const manual = MANUAL_PREFIX_PATTERN.test(verify);

    return {
      number: Number(match[1]),
      claim: match[3].trim(),
      checked: match[2].toLowerCase() === CHECKED_BOX,
      verify: manual ? this.stepOf(verify) : verify,
      manual,
    };
  }

  /** `manual: <step>` or `` `manual: <step>` ``: the step a human does. */
  private stepOf(verify: string): string {
    const step = verify.replace(MANUAL_PREFIX_PATTERN, '');

    return verify.startsWith('`') && step.endsWith('`') ? step.slice(0, -1) : step;
  }
}

export default AcceptanceCriteria;
