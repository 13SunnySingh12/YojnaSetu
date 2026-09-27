package com.yojnasetu.scheme;

import java.util.List;

/**
 * Comparable eligibility conditions taken only from official structured fields. A null or empty value
 * means the source states no comparable condition, never "anyone qualifies".
 */
public record EligibilityRules(
		Integer minAge,
		Integer maxAge,
		List<String> genders,
		List<String> states,
		List<String> socialCategories,
		List<String> occupations,
		Long maxAnnualIncome) {
}
