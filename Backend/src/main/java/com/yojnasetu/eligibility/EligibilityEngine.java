package com.yojnasetu.eligibility;

import java.util.ArrayList;
import java.util.List;

import com.yojnasetu.scheme.EligibilityRules;
import com.yojnasetu.scheme.IndianStates;

/**
 * Transparent field-by-field comparison of a user's answers with a scheme's stored conditions. No scoring
 * model: every outcome is explained by the conditions it lists.
 */
final class EligibilityEngine {

	enum Status {
		LIKELY_MATCH, NOT_A_MATCH, MORE_INFO_NEEDED
	}

	record Condition(String field, String requirement, String yourValue) {
	}

	record Outcome(Status status, List<Condition> matched, List<Condition> unmatched, List<Condition> missing) {
	}


	private EligibilityEngine() {
	}

	static Outcome evaluate(EligibilityRules rules, Profile profile) {
		List<Condition> matched = new ArrayList<>();
		List<Condition> unmatched = new ArrayList<>();
		List<Condition> missing = new ArrayList<>();
		if (rules != null) {
			if (rules.minAge() != null || rules.maxAge() != null) {
				String requirement = ageRequirement(rules.minAge(), rules.maxAge());
				if (profile.age() == null) {
					missing.add(new Condition("age", requirement, null));
				}
				else {
					boolean ok = (rules.minAge() == null || profile.age() >= rules.minAge())
							&& (rules.maxAge() == null || profile.age() <= rules.maxAge());
					(ok ? matched : unmatched).add(new Condition("age", requirement, profile.age() + " years"));
				}
			}
			compare("gender", "Gender: ", rules.genders(), profile.gender(), matched, unmatched, missing);
			compareStates(rules.states(), profile.state(), matched, unmatched, missing);
			compare("socialCategory", "Social category: ", rules.socialCategories(), profile.socialCategory(),
					matched, unmatched, missing);
			compare("occupation", "Occupation: ", rules.occupations(), profile.occupation(), matched, unmatched,
					missing);
			if (rules.maxAnnualIncome() != null) {
				String requirement = "Annual family income up to ₹" + rupees(rules.maxAnnualIncome());
				if (profile.annualIncome() == null) {
					missing.add(new Condition("annualIncome", requirement, null));
				}
				else {
					boolean ok = profile.annualIncome() <= rules.maxAnnualIncome();
					(ok ? matched : unmatched).add(new Condition("annualIncome", requirement,
							"₹" + rupees(profile.annualIncome())));
				}
			}
		}
		Status status;
		if (!unmatched.isEmpty()) {
			status = Status.NOT_A_MATCH;
		}
		else if (!missing.isEmpty() || matched.isEmpty()) {
			// With nothing comparable stored we cannot call it a match: the user must read the official rules.
			status = Status.MORE_INFO_NEEDED;
		}
		else {
			status = Status.LIKELY_MATCH;
		}
		return new Outcome(status, matched, unmatched, missing);
	}

	private static void compare(String field, String prefix, List<String> allowed, String value,
			List<Condition> matched, List<Condition> unmatched, List<Condition> missing) {
		if (!restricts(allowed)) {
			return;
		}
		String requirement = prefix + String.join(", ", allowed);
		if (value == null) {
			missing.add(new Condition(field, requirement, null));
			return;
		}
		boolean ok = allowed.stream().anyMatch(a -> sameCategory(a, value));
		(ok ? matched : unmatched).add(new Condition(field, requirement, value));
	}

	private static void compareStates(List<String> allowed, String state, List<Condition> matched,
			List<Condition> unmatched, List<Condition> missing) {
		if (!restricts(allowed)) {
			return;
		}
		String requirement = "State: " + String.join(", ", allowed);
		if (state == null) {
			missing.add(new Condition("state", requirement, null));
			return;
		}
		boolean ok = allowed.stream().anyMatch(a -> IndianStates.same(a, state));
		(ok ? matched : unmatched).add(new Condition("state", requirement, state));
	}

	/** An empty list, or one containing "All", states no restriction. */
	private static boolean restricts(List<String> allowed) {
		return allowed != null && !allowed.isEmpty() && allowed.stream().noneMatch(a -> a.equalsIgnoreCase("All"));
	}

	/** "Scheduled Caste (SC)" and "SC" name the same category; comparison ignores case. */
	private static boolean sameCategory(String official, String value) {
		String code = official.replaceAll(".*\\(([^)]+)\\)\\s*$", "$1");
		return official.equalsIgnoreCase(value) || code.equalsIgnoreCase(value);
	}

	/** Indian digit grouping (2,50,000); java.text.DecimalFormat supports only a single grouping size. */
	static String rupees(long amount) {
		String digits = Long.toString(amount);
		if (digits.length() <= 3) {
			return digits;
		}
		String head = digits.substring(0, digits.length() - 3).replaceAll("\\B(?=(\\d{2})+$)", ",");
		return head + "," + digits.substring(digits.length() - 3);
	}

	private static String ageRequirement(Integer min, Integer max) {
		if (min != null && max != null) {
			return "Age between " + min + " and " + max + " years";
		}
		return min != null ? "Age " + min + " years or above" : "Age up to " + max + " years";
	}

}
