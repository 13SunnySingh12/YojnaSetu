package com.yojnasetu.eligibility;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;

import org.junit.jupiter.api.Test;

import com.yojnasetu.eligibility.EligibilityEngine.Condition;
import com.yojnasetu.eligibility.EligibilityEngine.Outcome;
import com.yojnasetu.eligibility.EligibilityEngine.Status;
import com.yojnasetu.scheme.EligibilityRules;

class EligibilityEngineTests {

	static final Profile NOBODY = new Profile(null, null, null, null, null, null);

	static EligibilityRules rules(Integer minAge, Integer maxAge, List<String> genders, List<String> states,
			List<String> categories, List<String> occupations, Long maxIncome) {
		return new EligibilityRules(minAge, maxAge, genders, states, categories, occupations, maxIncome);
	}

	static List<String> fields(List<Condition> conditions) {
		return conditions.stream().map(Condition::field).toList();
	}

	@Test
	void schemeWithoutComparableConditionsNeedsMoreInformation() {
		assertThat(EligibilityEngine.evaluate(null, NOBODY).status()).isEqualTo(Status.MORE_INFO_NEEDED);
		Outcome empty = EligibilityEngine.evaluate(rules(null, null, List.of(), null, null, null, null),
				new Profile(30, "Bihar", "Male", "General", "Farmer", 1L));
		assertThat(empty.status()).isEqualTo(Status.MORE_INFO_NEEDED);
		assertThat(empty.matched()).isEmpty();
	}

	@Test
	void ageRangeMatchesInclusiveBoundsAndRejectsOutside() {
		EligibilityRules r = rules(18, 40, null, null, null, null, null);
		assertThat(EligibilityEngine.evaluate(r, new Profile(18, null, null, null, null, null)).status())
			.isEqualTo(Status.LIKELY_MATCH);
		assertThat(EligibilityEngine.evaluate(r, new Profile(40, null, null, null, null, null)).status())
			.isEqualTo(Status.LIKELY_MATCH);
		Outcome old = EligibilityEngine.evaluate(r, new Profile(41, null, null, null, null, null));
		assertThat(old.status()).isEqualTo(Status.NOT_A_MATCH);
		assertThat(old.unmatched()).containsExactly(new Condition("age", "Age between 18 and 40 years", "41 years"));
	}

	@Test
	void unansweredConditionIsReportedAsMissingInsteadOfGuessed() {
		Outcome outcome = EligibilityEngine.evaluate(rules(60, null, null, null, null, null, 200_000L), NOBODY);
		assertThat(outcome.status()).isEqualTo(Status.MORE_INFO_NEEDED);
		assertThat(fields(outcome.missing())).containsExactly("age", "annualIncome");
		assertThat(outcome.missing().get(0).requirement()).isEqualTo("Age 60 years or above");
	}

	@Test
	void aConflictOutweighsMissingInformation() {
		Outcome outcome = EligibilityEngine.evaluate(rules(null, 30, List.of("Female"), null, null, null, null),
				new Profile(null, null, "Male", null, null, null));
		assertThat(outcome.status()).isEqualTo(Status.NOT_A_MATCH);
		assertThat(fields(outcome.unmatched())).containsExactly("gender");
		assertThat(fields(outcome.missing())).containsExactly("age");
	}

	@Test
	void allMeansNoRestriction() {
		Outcome outcome = EligibilityEngine.evaluate(
				rules(null, null, List.of("All"), List.of("All"), List.of("all"), List.of("All"), null),
				new Profile(null, null, null, null, null, null));
		assertThat(outcome.matched()).isEmpty();
		assertThat(outcome.missing()).isEmpty();
		assertThat(outcome.status()).isEqualTo(Status.MORE_INFO_NEEDED);
	}

	@Test
	void officialLabelsMatchUserValuesAcrossSpellings() {
		Outcome outcome = EligibilityEngine.evaluate(
				rules(null, null, List.of("female"), List.of("Jammu & Kashmir"), List.of("Scheduled Caste (SC)"),
						List.of("Farmer"), null),
				new Profile(null, "Jammu and Kashmir", "Female", "SC", "farmer", null));
		assertThat(outcome.status()).isEqualTo(Status.LIKELY_MATCH);
		assertThat(fields(outcome.matched())).containsExactly("gender", "state", "socialCategory", "occupation");
	}

	@Test
	void rupeeAmountsUseIndianGrouping() {
		assertThat(EligibilityEngine.rupees(999)).isEqualTo("999");
		assertThat(EligibilityEngine.rupees(1_000)).isEqualTo("1,000");
		assertThat(EligibilityEngine.rupees(2_50_000)).isEqualTo("2,50,000");
		assertThat(EligibilityEngine.rupees(1_00_00_000)).isEqualTo("1,00,00,000");
	}

	@Test
	void incomeLimitUsesIndianDigitGrouping() {
		Outcome outcome = EligibilityEngine.evaluate(rules(null, null, null, null, null, null, 250_000L),
				new Profile(null, null, null, null, null, 1_20_000L));
		assertThat(outcome.status()).isEqualTo(Status.LIKELY_MATCH);
		assertThat(outcome.matched()).containsExactly(
				new Condition("annualIncome", "Annual family income up to ₹2,50,000", "₹1,20,000"));
		assertThat(EligibilityEngine.evaluate(rules(null, null, null, null, null, null, 250_000L),
				new Profile(null, null, null, null, null, 250_001L)).status()).isEqualTo(Status.NOT_A_MATCH);
	}

}
