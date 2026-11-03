"""014 source authority checklist. External reviewer evidence, never field naming."""
import re

REQUIRED = ('publisher_statement','availability_statement','sample_binding',
            'clock_authority','coverage_manifest','research_rights')


def assess_submission(submission, independently_verified_hashes=()):
    reasons = []
    independently_verified_hashes = set(independently_verified_hashes)
    if set(submission.get('assets',[])) != {'BTCUSDT','ETHUSDT'}:
        reasons.append('ASSET_COVERAGE_MISSING')
    if submission.get('period') != ['2025-01-01','2025-07-01']:
        reasons.append('HISTORICAL_SCOPE_NOT_ATTESTED')
    if submission.get('publication_semantics') != 'ISSUER_ORIGINAL_PUBLICATION':
        reasons.append('EVENT_OR_COLLECTOR_TIME_IS_NOT_PUBLICATION')
    for name in REQUIRED:
        value = submission.get(name)
        if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):
            reasons.append(name.upper()+'_MISSING')
        elif value not in independently_verified_hashes:
            reasons.append(name.upper()+'_INDEPENDENT_REVIEW_MISSING')
    if not all(submission.get(k) is True for k in ('bid_ask','rolling_24h_eligibility','gap_and_revision_manifest')):
        reasons.append('LIQUIDITY_OR_LINEAGE_INCOMPLETE')
    return dict(status='BLOCKED_EXTERNAL_EVIDENCE' if reasons else 'SOURCE_PASS_CANDIDATE_EXTERNAL_REVIEW_REQUIRED',
                reasons=reasons, scientific_acceptance=False, production_authorized=False)
