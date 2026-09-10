-- Two subscription terms covering the same day for one account means a
-- point-in-time join returns TWO rows instead of one - which silently doubles
-- MRR and seat counts for that account-month.
--
-- The self-join compares every pair of terms for an account once (s1.id < s2.id
-- avoids comparing a row to itself and avoids counting each pair twice).
-- Two intervals overlap when each starts before the other ends.
SELECT
    'subs_overlapping_terms'                        AS check_id,
    'subscriptions: terms must not overlap within an account' AS check_name,
    'raw.subscriptions'                             AS entity,
    'WARN'                                          AS severity,
    count(*)                                        AS failed_rows,
    'overlapping term pairs - these double-count on point-in-time joins' AS detail
FROM raw.subscriptions s1
JOIN raw.subscriptions s2
  ON s1.account_id = s2.account_id
 AND s1.subscription_id < s2.subscription_id
 AND s1.term_start_date < s2.term_end_date
 AND s2.term_start_date < s1.term_end_date;
