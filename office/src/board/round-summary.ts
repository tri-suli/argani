import { SUMMARY_SEPARATOR } from '@/constants/round';
import type { RoundTally } from '@/types/round';

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** The one sentence under the title of a round. It says only what the verdicts and the files read show. */
class RoundSummary {
  sentence(tally: RoundTally): string {
    return [this.reviewers(tally), this.findings(tally), this.notes(tally), this.unreadable(tally), this.human(tally)].filter((clause) => clause !== '').join(SUMMARY_SEPARATOR);
  }

  private reviewers(tally: RoundTally): string {
    const { seats, passed, changes, pending, invalid } = tally;

    const only = seats === 1;

    if (seats === 0) {
      return tally.hasHuman ? 'Only the human has written a request' : 'No review file in this round yet';
    }

    if (pending === seats) {
      return only ? 'The reviewer has not reported yet' : 'The reviewers have not reported yet';
    }

    if (pending + invalid === 0) {
      if (changes === 0) {
        return only ? 'The reviewer passed' : `All ${seats} reviewers passed`;
      }

      if (passed === 0) {
        return only ? 'The reviewer asked for changes' : `All ${seats} reviewers asked for changes`;
      }

      return `${changes} of ${seats} reviewers asked for changes`;
    }

    const parts = [
      changes > 0 ? `${changes} asked for changes` : '',
      passed > 0 ? `${passed} passed` : '',
      pending > 0 ? `${pending} not reported yet` : '',
      invalid > 0 ? `${invalid} gave no valid verdict` : '',
    ];

    return `Of ${seats} reviewers: ${parts.filter((part) => part !== '').join(', ')}`;
  }

  private findings(tally: RoundTally): string {
    const { important, nits, other } = tally;

    if (important + nits + other === 0) {
      // "no findings" only when every file was read and nothing was left unshown
      if (tally.read === 0 || tally.unreadable > 0 || tally.notes > 0) {
        return '';
      }

      return tally.pending > 0 ? 'no findings yet' : 'no findings';
    }

    return [
      important > 0 ? plural(important, 'important finding', 'important findings') : '',
      nits > 0 ? plural(nits, 'nit', 'nits') : '',
      other > 0 ? `${other} with another severity` : '',
    ].filter((part) => part !== '').join(', ');
  }

  private notes(tally: RoundTally): string {
    return tally.notes > 0 ? plural(tally.notes, 'note', 'notes') : '';
  }

  private unreadable(tally: RoundTally): string {
    return tally.unreadable > 0 ? `${plural(tally.unreadable, 'file', 'files')} could not be read` : '';
  }

  /** Said apart from the reviewers: the human's request is in the findings, not in the verdicts. */
  private human(tally: RoundTally): string {
    return tally.hasHuman && tally.seats > 0 ? 'includes a request from the human' : '';
  }
}

export default RoundSummary;
